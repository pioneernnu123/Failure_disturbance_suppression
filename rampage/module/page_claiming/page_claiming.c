
#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/init.h>
#include <linux/kernel.h>       
#include <linux/fs.h>           
#include <linux/errno.h>        
#include <linux/types.h>        
#include <linux/fcntl.h>        
#include <asm/uaccess.h>
#include <linux/mm.h>

#include "phys_mem.h"           
#include "phys_mem_int.h"           
#include "page_claiming.h"           

// LZU DSLAB CHANGE

#include <linux/ioport.h>
#include <linux/string.h>

// LZU DSLAB CHANGE

bool my_page_is_system_ram(unsigned long pfn)
{
    struct resource *res;
    resource_size_t start = (resource_size_t)pfn << PAGE_SHIFT;
    resource_size_t end = start + PAGE_SIZE - 1;

    for (res = iomem_resource.child; res; res = res->sibling) {
        if (!res->name)
            continue;

        if (strcmp(res->name, "System RAM") != 0)
            continue;

        if (start >= res->start && end <= res->end)
            return true;
    }

    return false;
}

#if 0
try_claim_method try_claim_methods[] = {
	try_claim_free_page,
	try_claim_free_buddy_page,
	try_claim_page_in_page_cache,
	try_claim_page_from_user_process,
	NULL
};
#endif

#if 0
try_claim_method try_claim_methods[] = {
	try_claim_free_page,
	try_claim_free_buddy_page,
	try_claim_page_in_page_cache,
	try_claim_page_from_user_process,
	ignore_difficult_pages,
	NULL
};
#endif

#if 0
try_claim_method try_claim_methods[] = {
	try_claim_free_buddy_page,
	NULL
};
#endif

#if 0
try_claim_method try_claim_methods[] = {
	ignore_difficult_pages,
	try_any_page_claiming,
	NULL
};
#endif

#if 0
try_claim_method try_claim_methods[] = {NULL};
#endif

try_claim_method try_claim_methods[] = {

	try_claim_free_buddy_page,
	ignore_difficult_pages,
	NULL
};

#if 0
#define DEBUG_REQUEST
#endif

#ifdef DEBUG_REQUEST
static void dump_request(struct phys_mem_session *session,
			 const struct phys_mem_request *request);
#endif

int handle_mark_page_poison(struct phys_mem_session *session,
			    const struct mark_page_poison *request)
{
	int ret = 0;

	if (down_interruptible(&session->sem))
		return -ERESTARTSYS;

	if (unlikely((GET_STATE(session) != SESSION_STATE_MAPPED)
		     && (GET_STATE(session) != SESSION_STATE_CONFIGURED))) {
		pr_warn("Session %llu: The state of the session is invalid: "
			"The Request  IOCTL should never appear in state %i\n",
			session->session_id, GET_STATE(session));
		ret = -EINVAL;
		goto out;
	}

	SetPageHWPoison(pfn_to_page(request->bad_pfn));
#if 0
	unsigned long i;
	for (i = 0; i < session->num_frame_stati; i++) {
		struct phys_mem_frame_status *status = &session->frame_stati[i];

		if (status->pfn == request->bad_pfn) {
			if (PFN_IS_CLAIMED(status) && status->page) {
				SetPageHWPoison(status->page);
# if 0
				pr_debug("Session %llu: The pfn %lu is now HW_POISONed\n",
					 session->session_id, request->bad_pfn);
# endif
				ret = 0;
				goto out;
			}
		} else {
# if 0
			pr_debug("Session %llu: The pfn %lu is not claimed for this session\n",
				 session->session_id, request->bad_pfn);
# endif
			ret = -EINVAL;
			goto out;
		}
	}

#endif

out:
	up(&session->sem);
	return ret;
}

int handle_request_pages(struct phys_mem_session *session,
			 const struct phys_mem_request *request)
{
	int ret = 0;
	unsigned long i;
	unsigned long current_offset_in_vma = 0;
	struct page * allocated_page;
	u64 jiffies_start, jiffies_end, jiffies_used;

	if (down_interruptible(&session->sem))
		return -ERESTARTSYS;

#ifdef DEBUG_REQUEST
	dump_request(session, request);
#endif

	if (unlikely((GET_STATE(session) != SESSION_STATE_OPEN)
		     && (GET_STATE(session) != SESSION_STATE_CONFIGURED))) {
		if (unlikely(GET_STATE(session) == SESSION_STATE_CONFIGURING))

			pr_notice("Session %llu: Racy configuring: The Request "
				  "IOCTL should never appear in state %i\n",
				  session->session_id, GET_STATE(session));
		else
			pr_warn("Session %llu: The state of the session is "
				"invalid: The Request  IOCTL should never "
				"appear in state %i\n",
				session->session_id, GET_STATE(session));
		ret = -EINVAL;
		goto out;
	}

	if (GET_STATE(session) == SESSION_STATE_CONFIGURED)
		free_page_stati(session);

	SET_STATE(session, SESSION_STATE_CONFIGURING);

	if (request->num_requests == 0) {
		SET_STATE(session, SESSION_STATE_OPEN);
		goto out;
	}

	session->frame_stati =
			SESSION_ALLOC_NUM_FRAME_STATI(request->num_requests);
	if (NULL == session->frame_stati) {
		ret = -ENOMEM;
		goto out_to_open;
	}

	memset(session->frame_stati, 0,
			SESSION_FRAME_STATI_SIZE(request->num_requests));
	session->num_frame_stati = request->num_requests;

	for (i = 0; i < request->num_requests; i++) {
		struct phys_mem_frame_request __user * current_pfn_request =
						&request->req[i];
		struct phys_mem_frame_status __kernel * current_pfn_status =
						&session->frame_stati[i];

		if (copy_from_user(&current_pfn_status->request,
				   current_pfn_request,
				   sizeof (struct phys_mem_frame_request))) {
			pr_alert("Session %llu: Failed to copy_from_user: Request #%lu\n",
				 session->session_id, i);
			ret = -EFAULT;
			goto out_to_open;
		}

		jiffies_start = get_jiffies_64();

		// LZU DSLAB CHANGE

		unsigned long req_pfn = current_pfn_status->request.requested_pfn;
		if (unlikely(!pfn_valid(req_pfn) || !my_page_is_system_ram(req_pfn))) {

			current_pfn_status->actual_source = SOURCE_INVALID_PFN;
#if 0
			pr_debug("Session %llu: Invalid pfn: %lu (at position #%lu)\n",
				  session->session_id,
				  current_pfn_status->request.requested_pfn, i);
#endif
		} else {
			struct page *requested_page = pfn_to_page(
				current_pfn_status->request.requested_pfn);
			try_claim_method claim_method = NULL;
			int claim_method_idx = 0;
			int claim_method_result = CLAIMED_TRY_NEXT;

			if (unlikely(NULL == requested_page)) {
				pr_notice("Session %llu: Invalid pfn: %lu (at position #%lu): pfn_to_page() returned NULL\n",
				    session->session_id,
				    current_pfn_status->request.requested_pfn,
				    i);
				ret = -EFAULT;
				goto out_to_open;
			}

			my_dump_page(requested_page, "Claiming: ");

			allocated_page = requested_page;

			while (CLAIMED_TRY_NEXT == claim_method_result) {
				claim_method = try_claim_methods[claim_method_idx];

				if (claim_method)
					claim_method_result = claim_method(
						requested_page,
						current_pfn_status->request.allowed_sources,
						&allocated_page,
						&current_pfn_status->actual_source);
				else
					claim_method_result = CLAIMED_ABORT;

				claim_method_idx++;
			}

			if (CLAIMED_SUCCESSFULLY == claim_method_result) {
				current_pfn_status->pfn =
						page_to_pfn(allocated_page);
				current_pfn_status->page = allocated_page;
				current_pfn_status->vma_offset_of_first_byte =
						current_offset_in_vma;
				current_offset_in_vma += PAGE_SIZE;
#if 0
				pr_debug("Session %llu: Claimed pfn %lx (requested page is %lx). "
					 "Method: %lx. Page-Count %i \n",
					 session->session_id, page_to_pfn(requested_page),
					 current_pfn_status->request.requested_pfn,
					 current_pfn_status->actual_source,
					 page_count(requested_page));
#endif
			} else {

				current_pfn_status->page = NULL;
				current_pfn_status->pfn = 0;
				current_pfn_status->vma_offset_of_first_byte = 0;
#if 0
				pr_debug("Session %llu: NOT Claimed pfn %lx (page is for %lx). "
					 "Method: %lx. Page-Count %i \n",
					 session->session_id,
					 current_pfn_status->request.requested_pfn,
					 page_to_pfn(requested_page),
					 current_pfn_status->actual_source,
					 page_count(requested_page));
#endif
			}

		}

		jiffies_end = get_jiffies_64();
		jiffies_used = jiffies_start < jiffies_end ? \
			       jiffies_end - jiffies_start : \
			       jiffies_start - jiffies_end;
		current_pfn_status->allocation_cost_jiffies = jiffies_used;
	}

	SET_STATE(session, SESSION_STATE_CONFIGURED);

out:
	up(&session->sem);
	return ret;

out_to_open:
	pr_notice("The Request IOCTL could not be completed!\n");
	free_page_stati(session);

	SET_STATE(session, SESSION_STATE_OPEN);

	up(&session->sem);
	return ret;
}

#ifdef DEBUG_REQUEST

static void dump_request(struct phys_mem_session *session,
			 const struct phys_mem_request *request)
{
	long int index = 0;

	if (!request)
		return;

#if 0
	pr_debug("Session %llu :Dumping %lu requested pages at %p:\n",
		 session->session_id, request->num_requests, request->req);
#endif

	if (request->req)
		for (index = 0; index < request->num_requests; index++) {

			long pfn, allowed_sources;
			get_user(pfn, &request->req[index].requested_pfn);
			get_user(allowed_sources,
				 &request->req[index].allowed_sources);

#if 0
			pr_debug("Session %llu: pfn %lu %lx \n",
				 session->session_id, pfn, allowed_sources);
#endif
		}
	else
		pr_notice("Session %llu: Dumping %lu requested pages: No Data\n",
			  session->session_id, request->num_requests);

#if 0
	pr_debug("Session %llu: DONE Dumping %lu requested pages:\n",
		 session->session_id, request->num_requests);
#endif

}
#endif
