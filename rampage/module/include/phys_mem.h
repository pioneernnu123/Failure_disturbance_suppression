
#ifndef PHYS_MEM__H_
#define PHYS_MEM__H_

#include <linux/ioctl.h>

#define PHYS_MEM_MAJOR	0

#define SOURCE_FREE_PAGE	0x00001

#define SOURCE_FREE_BUDDY_PAGE	0x00002

#define SOURCE_PAGE_CACHE	0x00004

#define SOURCE_ANONYMOUS	0x00008

#define SOURCE_ANY_PAGE		0x00010

#define SOURCE_HW_POISON_ANON	0x00020

#define SOURCE_HW_POISON_PAGE_CACHE	0x00040

#define SOURCE_HW_POISON \
	(SOURCE_HW_POISON_ANON | SOURCE_HW_POISON_PAGE_CACHE)

#define SOURCE_HOTPLUG		0x00080

#define SOURCE_SHAKING		0x00100

#define SOURCE_HOTPLUG_CLAIM	0x00200

#define SOURCE_INVALID_PFN	0x80000

#define SOURCE_ERROR_NOT_MAPPABLE	0x100000

#define SOURCE_MASK		0x000FFFFF
#define SOURCE_ERROR_MASK	0xFFF00000

#define PFN_IS_CLAIMED(phys_mem_frame_status) \
	((phys_mem_frame_status->actual_source & SOURCE_MASK) != 0)

struct phys_mem_frame_request {
	unsigned   long requested_pfn;
	unsigned  long allowed_sources; 
};

struct phys_mem_frame_status {
	struct phys_mem_frame_request request;

	unsigned long long vma_offset_of_first_byte;

	unsigned  long pfn;

	unsigned long long allocation_cost_jiffies;

	unsigned  long actual_source;

	struct page *page;
};

extern int phys_mem_major;     
extern int phys_mem_devs;
extern int phys_mem_order;
extern int phys_mem_qset;

#define IOCTL_REQUEST_VERSION   1

struct phys_mem_request {

	unsigned  long protocol_version;

	unsigned  long num_requests;

	struct phys_mem_frame_request *req;
};

struct mark_page_poison {

	unsigned  long protocol_version;

	unsigned  long bad_pfn;
};

#define PHYS_MEM_IOC_MAGIC  'K'

#define PHYS_MEM_IOC_REQUEST_PAGES \
		_IOW(PHYS_MEM_IOC_MAGIC, 0, struct phys_mem_request )

#define PHYS_MEM_IOC_MARK_FRAME_BAD \
		_IOW(PHYS_MEM_IOC_MAGIC, 1, struct mark_page_poison )

#define PHYS_MEM_IOC_MAXNR 1

#endif
