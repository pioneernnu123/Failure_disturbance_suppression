
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

#include <linux/pageblock-flags.h>

#include "phys_mem.h"           
#include "phys_mem_int.h"           
#include "page_claiming.h"           

#include <linux/page_ref.h> // LZU DSLAB CHANGE

static inline int free_pages_check__just_test(struct page *page)
{
	if (unlikely(page_mapcount(page) |(page->mapping != NULL) |

//		LZU DSLAB CHANGE
		(page_ref_count(page) != 0) |
		(page->flags & PAGE_FLAGS_CHECK_AT_FREE)))
		return 1;
	return 0;
}

inline int try_claim_free_page(struct page *requested_page,
			       unsigned int allowed_sources,
			       struct page **allocated_page,
			       unsigned long *actual_source)
{
	int ret = CLAIMED_TRY_NEXT;
	int enabled = 0;

	if (enabled && (allowed_sources & SOURCE_FREE_PAGE)) {
		struct page *compound_head_page;

		compound_head_page = compound_head(requested_page);

		if (compound_head_page == requested_page
			&& !free_pages_check__just_test(requested_page) == 0
			&& requested_page->lru.next == NULL
			&& requested_page->lru.prev == NULL) {
			int locked_page_count_before, locked_page_count_after;

			locked_page_count_before = page_count(requested_page);
			get_page(requested_page);

			if (requested_page) {

				locked_page_count_after =
						page_count(requested_page);
				pr_debug("Requested pfn %lx  with pagecount %i (was:%i)\n",
					 page_to_pfn(requested_page),
					 locked_page_count_after,
					 locked_page_count_before);
				*actual_source = SOURCE_FREE_PAGE;
				ret = CLAIMED_SUCCESSFULLY;
			} else {

				pr_debug("Requested pfn %lx but could not get it "
					 "though it was _count == 0.)\n",
					 page_to_pfn(requested_page));
			}
		}
	}
	return ret;
}
