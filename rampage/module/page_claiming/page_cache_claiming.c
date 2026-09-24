
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

int try_claim_page_in_page_cache(struct page *requested_page,
				 unsigned int allowed_sources,
				 struct page **allocated_page,
				 unsigned long *actual_source)
{
	int ret = CLAIMED_TRY_NEXT;

	if ( allowed_sources & SOURCE_PAGE_CACHE) {

	}
	return ret;
}
