
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
#include <linux/memory_hotplug.h>
#include <linux/pageblock-flags.h>

#include "phys_mem.h"           
#include "phys_mem_int.h"       
#include "page_claiming.h"      

#define OFFLINE_AT_ONCE (1 << MAX_ORDER)

static u64 start_address = -1;
static u64 prev_start_address = -1;
static u64 prev_failed_claim = -1;

void unclaim_pages_via_hotplug(struct page *requested_page)
{
	unsigned long pfn = page_to_pfn(requested_page);
	u64 address = pfn << PAGE_SHIFT;
	u64 aligned_address = address &
			~(((unsigned long)OFFLINE_AT_ONCE << PAGE_SHIFT) - 1UL);
	int ret;

	if (aligned_address != start_address
	    && aligned_address != prev_start_address) {
		pr_crit("physmem: Attempted to unclaim_pages_via_hotplug on nonclaimed area!\n");
		return;
	}

	if (start_address != -1) {

		ret = online_pages(aligned_address >> PAGE_SHIFT, OFFLINE_AT_ONCE);
		if (ret) {
			pr_crit("physmem: unclaim failed for pfn %08llx: ret %d\n",
				aligned_address >> PAGE_SHIFT, ret);
		}

		prev_start_address = start_address;
		start_address = -1;
	} else {

		return;
	}
}

int try_claim_pages_via_hotplug(struct page *requested_page,
				unsigned int allowed_sources,
				struct page **allocated_page,
				unsigned long *actual_source)
{
	if (allowed_sources & SOURCE_HOTPLUG_CLAIM) {
		unsigned long pfn = page_to_pfn(requested_page);
		u64 address = pfn << PAGE_SHIFT;
		u64 aligned_address = address &
			~(((unsigned long)OFFLINE_AT_ONCE << PAGE_SHIFT) - 1UL);
		int ret;

		if (start_address != -1) {
			if (aligned_address == start_address) {

				*actual_source = SOURCE_HOTPLUG_CLAIM;
				return CLAIMED_SUCCESSFULLY;
			} else {

				return CLAIMED_TRY_NEXT;
			}
		}

		if (prev_failed_claim == aligned_address)
			return CLAIMED_TRY_NEXT;

		if (aligned_address == 0)
			return CLAIMED_TRY_NEXT;

		ret = remove_memory(aligned_address,
				    OFFLINE_AT_ONCE << PAGE_SHIFT);
		if (ret) {
			if (allowed_sources & SOURCE_SHAKING) {

				shake_page(requested_page, 1);
				ret = remove_memory(aligned_address,
						OFFLINE_AT_ONCE << PAGE_SHIFT);
				if (ret) {
					prev_failed_claim = aligned_address;
					return CLAIMED_TRY_NEXT;
				}
			} else {

				prev_failed_claim = aligned_address;
				return CLAIMED_TRY_NEXT;
			}
		}

		start_address = aligned_address;
		prev_start_address = -1;
		*actual_source = SOURCE_HOTPLUG_CLAIM;
		return CLAIMED_SUCCESSFULLY;
	}

	return CLAIMED_TRY_NEXT;
}

