#ifndef GPGPU_H_INCLUDED
#define GPGPU_H_INCLUDED

#include "CL/cl.h"

#define MAX_SL_PLATFORMS 4
#define MAX_SL_DEVICES 4
#define MAX_SL_CONTEXTS 1
#define MAX_SL_QUEUES MAX_SL_DEVICES
#define MAX_DIMENSIONS 4


enum // preferred_type
{
    SL_PLATFORM_BEST,
};

struct shape_t
{
    cl_uint dim;
    size_t global_offset[MAX_DIMENSIONS];
    size_t global_size[MAX_DIMENSIONS];
    size_t local_size[MAX_DIMENSIONS];
};


extern cl_platform_id   SL_platforms[MAX_SL_PLATFORMS];
extern int              SL_platforms_len;
extern cl_device_id     SL_devices[MAX_SL_PLATFORMS][MAX_SL_DEVICES];
extern int              SL_devices_len[MAX_SL_PLATFORMS];
extern cl_context       SL_context;
extern cl_command_queue SL_queues[MAX_SL_PLATFORMS][MAX_SL_QUEUES];
extern int              SL_queues_len[MAX_SL_PLATFORMS];



int SL_init(cl_device_type device_flags);
int SL_use_platform(int preferred_type);
int SL_init_from_platform(int platform_id);
int SL_init_from_device(int platform_id, int device_id);
int SL_init_queues_on_platform(int platform_id);
int SL_init_queue_on_device(int platform_id, int device_id);

int SL_finish_queues_on_platform(int platform_id);
int SL_finish_queue(int platform_id, int device_id);

cl_kernel SL_compile_text(int platform_id, int device_id, const char *kernel_function_name, const char *source_code, size_t source_length, int *ret_err);
cl_kernel SL_compile_file(int platform_id, int device_id, const char *kernel_function_name, const char *filename, int *ret_err);

cl_mem SL_alloc(size_t size, cl_mem_flags flags, int *ret_err);
cl_mem SL_share(size_t size, cl_mem_flags flags, void *host_ptr, int *ret_err);

int SL_run(int platform_id, int comand_queue_id, cl_kernel kernel, struct shape_t config_shape);
int SL_run_use_shape_local(int platform_id, int comand_queue_id, cl_kernel kernel, struct shape_t config_shape);

#endif // GPGPU_H_INCLUDED
