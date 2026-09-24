
#ifndef PAGE_CLAIMING_H_
#define PAGE_CLAIMING_H_

int handle_request_pages(struct phys_mem_session *,
			 const struct phys_mem_request *);

int handle_mark_page_poison(struct phys_mem_session *session,
			    const struct mark_page_poison *request);

#define CLAIMED_SUCCESSFULLY	1

#define CLAIMED_TRY_NEXT	2

#define CLAIMED_ABORT		3

typedef int (*try_claim_method)(struct page *requested_page,
				unsigned int allowed_sources,
				struct page **allocated_page,
				unsigned long *actual_source);

int try_claim_page_from_user_process(struct page *requested_page,
				     unsigned int allowed_sources,
				     struct page **allocated_page,
				     unsigned long *actual_source);

int try_claim_page_in_page_cache(struct page *requested_page,
				 unsigned int allowed_sources,
				 struct page **allocated_page,
				 unsigned long *actual_source);

int try_claim_free_page(struct page *requested_page,
			unsigned int allowed_sources,
			struct page **allocated_page,
			unsigned long *actual_source);

int try_claim_free_buddy_page(struct page *requested_page,
			      unsigned int allowed_sources,
			      struct page **allocated_page,
			      unsigned long *actual_source);

int try_claim_page_via_hwpoison(struct page *requested_page,
				unsigned int allowed_sources,
				struct page **allocated_page,
				unsigned long *actual_source);

int try_any_page_claiming(struct page *requested_page,
			  unsigned int allowed_sources,
			  struct page **allocated_page,
			  unsigned long *actual_source);

int ignore_difficult_pages(struct page *requested_page,
			   unsigned int allowed_sources,
			   struct page **allocated_page,
			   unsigned long *actual_source);

int free_pages_via_hotplug(struct page *requested_page,
			   unsigned int allowed_sources,
			   struct page **allocated_page,
			   unsigned long *actual_source);

int try_claim_pages_via_hotplug(struct page *requested_page,
				unsigned int allowed_sources,
				struct page **allocated_page,
				unsigned long *actual_source);

void my_dump_page(struct page *page, char *msg);

#endif 
