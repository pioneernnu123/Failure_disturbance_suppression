
#ifndef PHYS_MEM_INT_H_
#define PHYS_MEM_INT_H_

#include <linux/ioctl.h>
#include <linux/cdev.h>
#include <linux/vmalloc.h>
#include <linux/semaphore.h>

#include "phys_mem.h"

struct phys_mem_dev {
	struct phys_mem_dev *next;  
	struct semaphore sem;     
	struct cdev cdev;
};

#define SESSION_STATE_CLOSED         0
#define SESSION_STATE_OPEN           1
#define SESSION_STATE_CONFIGURING    2
#define SESSION_STATE_CONFIGURED     3
#define SESSION_STATE_MAPPED         4

#define SESSION_STATE_INVALID        5

#define SESSION_NUM_STATES           5

#define GET_STATE(session) ((session)->status.state)
#define SET_STATE(session,value) set_state((session),(value))

struct session_status {
	unsigned int state;
};

struct phys_mem_session {
	struct session_status status;
	unsigned long long    session_id;
	int vmas;                              
	struct phys_mem_dev *  device;
	struct semaphore       sem;            
	unsigned long          num_frame_stati;     
	struct phys_mem_frame_status *frame_stati; 
};

extern struct phys_mem_dev *phys_mem_devices;

void free_page_stati(struct phys_mem_session *session);

#define     SESSION_FRAME_STATI_SIZE(num)  (num) * sizeof(struct phys_mem_frame_status)

#define     SESSION_FREE_FRAME_STATI(p) vfree(p)
#define     SESSION_ALLOC_NUM_FRAME_STATI(num) vmalloc( SESSION_FRAME_STATI_SIZE(num) )

extern struct file_operations phys_mem_fops;
extern struct kmem_cache *session_mem_cache;

static __attribute__((unused)) char * SESSION_STATE_TXT[] = {
	"SESSION_STATE_CLOSED",
	"SESSION_STATE_OPEN",
	"SESSION_STATE_CONFIGURING",
	"SESSION_STATE_CONFIGURED",
	"SESSION_STATE_MAPPED",
	"- INVALID -"
};

static inline void set_state(struct phys_mem_session * session,
			     unsigned int new_state) {
	if (new_state >= SESSION_NUM_STATES)
		new_state = SESSION_STATE_INVALID;

#if 0
	pr_debug("Session %llu: %s -> %s\n",session->session_id,
		  SESSION_STATE_TXT[GET_STATE(session)], SESSION_STATE_TXT[new_state]) ;
#endif

	session->status.state = new_state;
}

#endif 
