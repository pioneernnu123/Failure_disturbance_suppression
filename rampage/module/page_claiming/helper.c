
#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/init.h>
#include <linux/kernel.h>       

#include <linux/mm.h>

void my_dump_page(struct page *page, char *msg)
{
#if 0
	if (!msg)
		msg="";

	if (page)
		pr_debug("%s page #%lu: flags: %lx Count: %i, Mapcount: %i, Mapping/private/first_page/... %p. Index: %lu. lru.next: %p / prev: %p\n",
			 msg, page_to_pfn(page), page->flags, page_count(page),
			 page_mapcount(page), page->mapping, page->index,
			 page->lru.next, page->lru.prev);
	else
		pr_debug("%s page NULL\n", msg);
#endif
}
