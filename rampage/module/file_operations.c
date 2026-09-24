
#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/init.h>
#include <linux/kernel.h>       
#include <linux/fs.h>           
#include <linux/errno.h>        
#include <linux/types.h>        
#include <linux/fcntl.h>        
#include <asm/uaccess.h>

#include <linux/slab.h>

#include "phys_mem.h"           
#include "phys_mem_int.h"           
#include "page_claiming.h"           
#include "mmap_phys.h"

atomic64_t session_counter = ATOMIC_INIT(0);

int phys_mem_open(struct inode *inode, struct file *filp)
{
	struct phys_mem_dev *dev; 
	struct phys_mem_session *session; 

	dev = container_of(inode->i_cdev, struct phys_mem_dev, cdev);

	session = kmem_cache_alloc(session_mem_cache, GFP_KERNEL);

	if (!session)
		return -ENOMEM;

	session->session_id = atomic64_add_return(1, &session_counter);
	session->device = dev;
	sema_init(&session->sem, 1);
	session->vmas = 0;
	session->num_frame_stati = 0;
	session->frame_stati = NULL;
	session->status.state = SESSION_STATE_INVALID;

	SET_STATE(session, SESSION_STATE_OPEN);

	filp->private_data = session;

	return 0; 
}

int phys_mem_release(struct inode *inode, struct file *filp)
{
	struct phys_mem_session *session; 

	session = (struct phys_mem_session *) filp->private_data;

	if (down_interruptible(&session->sem))
		return -ERESTARTSYS;

	while (GET_STATE(session) != SESSION_STATE_CLOSED) {
		switch (GET_STATE(session)) {
		case SESSION_STATE_OPEN:

			session->device = NULL;
			session->vmas = 0;
			SET_STATE(session, SESSION_STATE_CLOSED);
			break;

		case SESSION_STATE_CONFIGURING:

			pr_warn("Session %llu: Releasing device while it is "
				"impossible (SESSION_STATE_CONFIGURING)\n",
				session->session_id);
			up(&session->sem);
			return -ERESTARTSYS;

		case SESSION_STATE_CONFIGURED:

			free_page_stati(session);
			SET_STATE(session, SESSION_STATE_OPEN);
			break;

		case SESSION_STATE_MAPPED: break;

			if (session->vmas)
				pr_notice("Session %llu: Releasing device "
					  "while it still holds %d mappings "
					  "(SESSION_STATE_MAPPED)\n ",
					  session->session_id, session->vmas);
			SET_STATE(session, SESSION_STATE_CONFIGURED);
			break;
		}
	}

	up(&session->sem);
	kmem_cache_free(session_mem_cache, session);
	return 0;
}

ssize_t file_read_configured(struct file *filp, char __user *buf,
			     size_t count, loff_t *f_pos)
{
	ssize_t retval = 0, max_size = 0;
	struct phys_mem_session *session =
				(struct phys_mem_session *) filp->private_data;

	if (down_interruptible(&session->sem))
		return -ERESTARTSYS;

	if ((GET_STATE(session) != SESSION_STATE_CONFIGURED)
	    && (GET_STATE(session) != SESSION_STATE_MAPPED)) {
		retval = -EIO;
		pr_notice("Session %llu: The session cannot be read in state %i",
			   session->session_id, GET_STATE(session));
		goto nothing;
	}

	max_size = SESSION_FRAME_STATI_SIZE(session->num_frame_stati);

	if (*f_pos > max_size)
		goto nothing;
	if (*f_pos + count > max_size)
		count = max_size - *f_pos;

	if (copy_to_user(buf, ((void *)((unsigned long)session->frame_stati)
				 + *f_pos), count)) {
		retval = -EFAULT;
		goto nothing;
	}

#if 0
	pr_debug("Session %llu: read OK  %08lli, %zi with max_size: %zi From %lli to %lli \n",
		  session->session_id, *f_pos, count, max_size,
		  *f_pos, *f_pos + count);
#endif

	up(&session->sem);

	*f_pos += count;
	return count;

nothing:
#if 0
	pr_debug("Session %llu: read ERR %08lli, %zi with max_size: %zi (p+s = %lli) -> %zi\n",
		  session->session_id, *f_pos, count, max_size,
		  *f_pos + count, retval);
#endif
	up(&session->sem);
	return retval;
}

long file_ioctl_open(struct file *filp, unsigned int cmd, unsigned long arg)
{
	int err = 0, ret = 0;
	struct phys_mem_session *session =
				(struct phys_mem_session *) filp->private_data;

#if 0
	pr_debug("Session %llu: file_ioctl_open: %x Type: %c (expect %c), Number %i Arg: %p\n",
		 session->session_id, cmd, _IOC_TYPE(cmd),
		 PHYS_MEM_IOC_MAGIC, _IOC_NR(cmd), (void *) arg);
#endif

	if (_IOC_TYPE(cmd) != PHYS_MEM_IOC_MAGIC)
		return -ENOTTY;
	if (_IOC_NR(cmd) > PHYS_MEM_IOC_MAXNR)
		return -ENOTTY;

	if (_IOC_DIR(cmd) & _IOC_READ) {

		// LZU DSLAB CHANGE
		err = !access_ok((void __user *)arg,
				 _IOC_SIZE(cmd));
	} else if (_IOC_DIR(cmd) & _IOC_WRITE) {

		// LZU DSLAB CHANGE
		err = !access_ok((void __user *)arg,
				 _IOC_SIZE(cmd));
	}
	if (err)
		return -EFAULT;

	switch (cmd) {
        case PHYS_MEM_IOC_REQUEST_PAGES:
		{

			struct phys_mem_request request;

			if (copy_from_user(&request,
					(struct phys_mem_request __user *)arg,
					   sizeof (struct phys_mem_request))) {
				pr_debug("Session %llu: file_ioctl_open: copy_from_user failed. \n",
					  session->session_id);
				ret = -EFAULT;
			} else {
#if 0
				pr_debug("Session %llu: request: Ver %lu, %lu items @%p\n",
						session->session_id,
						request.protocol_version,
						request.num_requests, request.req);
#endif
				if (request.protocol_version
				    != IOCTL_REQUEST_VERSION)
					ret = -EINVAL;
				else
					ret = handle_request_pages(session,
								   &request);
			}
			break;
		}
	case PHYS_MEM_IOC_MARK_FRAME_BAD:
		{

			struct mark_page_poison request;

			if (copy_from_user(&request,
					(struct mark_page_poison __user *)arg,
					sizeof(struct mark_page_poison))) {
				pr_debug("Session %llu: file_ioctl_open: copy_from_user failed. \n",
					  session->session_id);
				ret = -EFAULT;
			} else {
#if 0
				pr_debug("Session %llu: request: Ver %lu,  pfn: %lu  \n",
					  session->session_id,
					  request.protocol_version,
					  request.bad_pfn);
#endif
				if (request.protocol_version
				    != IOCTL_REQUEST_VERSION)
					ret = -EINVAL;
				else
					ret = handle_mark_page_poison(session,
								      &request);
			}
			break;
		}
	default:

		pr_debug("Session %llu: file_ioctl_open: default %d\n",
			  session->session_id, cmd);
		return -ENOTTY;
	}

	return ret;
}

loff_t file_llseek_configured(struct file *filp, loff_t off, int whence)
{
	struct phys_mem_session *session =
				(struct phys_mem_session *) filp->private_data;
	size_t max_size = 0;
	long newpos = 0;
	long error = 0;

	if (down_interruptible(&session->sem))
		return -ERESTARTSYS;

	if ((GET_STATE(session) != SESSION_STATE_CONFIGURED)
	    && (GET_STATE(session) != SESSION_STATE_MAPPED)) {
		error = -EIO;
		pr_notice("Session %llu: The session cannot be llseek in state %i",
			   session->session_id, GET_STATE(session));
		goto err;
	}

	max_size = SESSION_FRAME_STATI_SIZE(session->num_frame_stati);

	switch (whence) {
	case 0: 
		newpos = off;
		break;
	case 1: 
		newpos = filp->f_pos + off;
		break;
	case 2: 
		newpos = max_size + off;
		break;
	default: 
		error = -EINVAL;
		goto err;
	}

	if (newpos < 0) {
		error = -EINVAL;
		goto err;
	}
#if 0
	pr_debug("Session %llu:  llseek OK   %08lli, %i with max_size: %li  From %lli to %li \n",
		  session->session_id, off, whence,
		  max_size, filp->f_pos, newpos);
#endif
	filp->f_pos = newpos;

	up(&session->sem);
	return newpos;
err:
#if 0
	pr_debug("Session %llu:  llseek ERR  %08lli, %i with max_size: %li  From %lli to %li \n",
		  session->session_id, off, whence,
		  max_size, filp->f_pos, newpos);
#endif
	up(&session->sem);
	return error;
}

struct file_operations fops_by_session_state[] = {
	{

		.llseek = NULL,
		.read = NULL,
		.unlocked_ioctl = NULL,
		.mmap = NULL,
	},
	{

		.llseek = NULL,
		.read = NULL,
		.unlocked_ioctl = file_ioctl_open,
		.mmap = NULL,
	},
	{

		.llseek = NULL,
		.read = NULL,
		.unlocked_ioctl = NULL,
		.mmap = NULL,
	},
	{

		.llseek = file_llseek_configured,
		.read = file_read_configured,
		.unlocked_ioctl = file_ioctl_open,
		.mmap = file_mmap_configured,
	},
	{

		.llseek = file_llseek_configured,
		.read = file_read_configured,
		.unlocked_ioctl = NULL,
		.mmap = file_mmap_configured,
	},
};

loff_t dispatch_llseek(struct file *filp, loff_t off, int whence)
{
	struct phys_mem_session * session = filp->private_data;
	loff_t (*fn) (struct file *, loff_t, int);

	if (session->status.state >= SESSION_NUM_STATES) {
		pr_err("Seeking with an invalid session state of %i!\n",
			session->status.state);
		return -EIO;
	}

	fn = fops_by_session_state[session->status.state].llseek;

	if (fn)
		return fn(filp, off, whence);
	else {
		pr_notice("Session %llu:  llseek not supported in state %i\n",
			   session->session_id, session->status.state);
		return -EIO;
	}
}

ssize_t dispatch_read(struct file *filp, char __user *buf, size_t count,
		      loff_t *f_pos)
{
	struct phys_mem_session * session = filp->private_data;
	ssize_t(*fn) (struct file *, char __user *, size_t, loff_t *);

	if (session->status.state >= SESSION_NUM_STATES) {
		pr_err("Reading with an invalid session state of %i!\n",
			session->status.state);
		return -EIO;
	}

	fn = fops_by_session_state[session->status.state].read;

	if (fn)
		return fn(filp, buf, count, f_pos);
	else {
		pr_notice("Session %llu:  read not supported in state %i\n",
			   session->session_id, session->status.state);
		return -EIO;
	}
}

long dispatch_ioctl(struct file *filp, unsigned int cmd, unsigned long arg)
{
	struct phys_mem_session * session = filp->private_data;
	long (*fn) (struct file *, unsigned int, unsigned long);
#if 0
	pr_debug("IOCTL:session state of %i!\n", session->status.state);
#endif

	if (session->status.state >= SESSION_NUM_STATES) {
		pr_err("IOCTL with an invalid session state of %i!\n",
			session->status.state);
		return -EIO;
	}

	fn = fops_by_session_state[session->status.state].unlocked_ioctl;

	if (fn)
		return fn(filp, cmd, arg);
	else {
		pr_notice("Session %llu:  ioctl not supported in state %i\n",
			   session->session_id, session->status.state);
		return -EIO;
	}
}

int dispatch_mmap(struct file * filp, struct vm_area_struct * vma)
{

	struct phys_mem_session * session = filp->private_data;
	int (*fn) (struct file *, struct vm_area_struct *);
#if 0
	pr_notice("Session %llu:  mmap \n", (session->session_id));
#endif

	if (session->status.state >= SESSION_NUM_STATES) {
		pr_err("mmap with an invalid session state of %i!\n",
			session->status.state);
		return -EIO;
	}

	fn = fops_by_session_state[session->status.state].mmap;

	if (fn)
		return fn(filp, vma);
	else {
		pr_notice("Session %llu:  mmap not supported in state %i \n",
			  session->session_id, session->status.state);
		return -EIO;
	}
}

struct file_operations phys_mem_fops = {
	.owner		= THIS_MODULE,
	.llseek		= dispatch_llseek,
	.read		= dispatch_read,
	.unlocked_ioctl	= dispatch_ioctl,
	.open		= phys_mem_open,
	.release	= phys_mem_release,
	.mmap		= dispatch_mmap,
};
