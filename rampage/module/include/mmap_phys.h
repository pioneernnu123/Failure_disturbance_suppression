
#ifndef MMAP_PHYS_H_
#define MMAP_PHYS_H_

extern struct vm_operations_struct phys_mem_vm_ops;

int file_mmap_configured(struct file *, struct vm_area_struct *);

#endif 
