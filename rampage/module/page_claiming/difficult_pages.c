
#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/init.h>
#include <linux/kernel.h>       
#include <linux/errno.h>        
#include <linux/mm.h>
#include <linux/pageblock-flags.h>
#include <asm-generic/sections.h> 
#include <asm/io.h>

#include "phys_mem_int.h"           
#include "page_claiming.h"           

#define pfn(address) page_to_pfn(virt_to_page(((void *)(address))))

int ignore_difficult_pages(struct page *requested_page,
                           unsigned int allowed_sources,
                           struct page **allocated_page,
                           unsigned long *actual_source)
{
	int ret = CLAIMED_TRY_NEXT;

	unsigned int is_first_mb = (page_to_phys(requested_page) <= 0x400 );

	unsigned int is_kernel_code = ((page_to_phys(requested_page) <= 0x800)
				       && !is_first_mb);

	if (is_first_mb || is_kernel_code)
		ret = CLAIMED_ABORT;

	return ret;
}
