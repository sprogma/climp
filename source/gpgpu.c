#include "stdio.h"
#include "CL\cl.h"
#include "gpgpu.h"

#define log(...) printf(__VA_ARGS__);


cl_platform_id   SL_platforms[MAX_SL_PLATFORMS];
int              SL_platforms_len;
cl_device_id     SL_devices[MAX_SL_PLATFORMS][MAX_SL_DEVICES];
int              SL_devices_len[MAX_SL_PLATFORMS];
cl_context       SL_context;
cl_command_queue SL_queues[MAX_SL_PLATFORMS][MAX_SL_QUEUES];
int              SL_queues_len[MAX_SL_PLATFORMS];

int SL_best_platform = 0;
int SL_best_platform_value = 0;


int SL_init(cl_device_type device_flags)
{
    int err;
    unsigned int read_count;

    // initialize cl (int * == unsigned int *, if number is little.)
    err = clGetPlatformIDs(MAX_SL_PLATFORMS, SL_platforms, (unsigned int *)&SL_platforms_len);
    if (err) { return err; }
    if (SL_platforms_len > MAX_SL_PLATFORMS)
    {
        SL_platforms_len = MAX_SL_PLATFORMS;
    }
    log("Got at least %d platforms\n", SL_platforms_len)
    // print them
    for (int i = 0; i < SL_platforms_len; ++i)
    {
        size_t allocated = 100;
        size_t info_len = 0;
        char *info = malloc(100), *tmp = NULL;
        printf("Platform %d:\n", i);
        #define PRINT(type, ...) \
        clGetPlatformInfo(SL_platforms[i], type, 0, NULL, &info_len); /* get size */ \
        if (allocated < info_len) \
        { \
            allocated = info_len; \
            tmp = info; info = realloc(info, info_len); \
            if (!info) { free(tmp); return 57; }\
        } \
        clGetPlatformInfo(SL_platforms[i], type, info_len, info, NULL); /* get value */ \
        log(__VA_ARGS__, info)
        #define PRINV(type, typename, ...) \
        clGetPlatformInfo(SL_platforms[i], type, 0, NULL, &info_len); /* get size */ \
        if (allocated < info_len) \
        { \
            allocated = info_len; \
            tmp = info; info = realloc(info, info_len); \
            if (!info) { free(tmp); return 57; }\
        } \
        clGetPlatformInfo(SL_platforms[i], type, info_len, info, NULL); /* get value */ \
        log(__VA_ARGS__, *(typename *)info)
        PRINT(CL_PLATFORM_NAME,                                 "\t%d.Name             : %s\n", i)
        PRINT(CL_PLATFORM_VENDOR,                               "\t%d.Vendor           : %s\n", i)
        PRINT(CL_PLATFORM_VERSION,                              "\t%d.Version          : %s\n", i)
        PRINT(CL_PLATFORM_PROFILE,                              "\t%d.Profile          : %s\n", i)
        PRINT(CL_PLATFORM_EXTENSIONS,                           "\t%d.Extensions       : %s\n", i)
        PRINV(CL_PLATFORM_HOST_TIMER_RESOLUTION, unsigned long, "\t%d.Timer Resolution : %lu\n", i)
        #undef PRINT
        #undef PRINV
        free(info);
        putchar('\n');

        int value = 0;
        value += 0;
        if (value > SL_best_platform_value)
        {
            SL_best_platform = i;
            SL_best_platform_value = value;
        }
    }

    putchar('\n');

    // load all devices
    int count = 0;
    for (int i = 0; i < SL_platforms_len; ++i)
    {
        err = clGetDeviceIDs(SL_platforms[i],
                       device_flags,
                       MAX_SL_DEVICES,
                       SL_devices[i],
                       &read_count);
        if (err) { return err; }
        if (read_count > MAX_SL_DEVICES)
        {
            read_count = MAX_SL_DEVICES;
        }
        log("platform %d: Got at least %u devices\n", i, read_count)
        SL_devices_len[i] = read_count;
        // print them
        for (int dev = 0; dev < SL_devices_len[i]; ++dev)
        {
            size_t allocated = 100;
            size_t info_len = 0;
            unsigned dims = -1;
            char *info = malloc(100), *tmp = NULL;
            printf("Device %d:\n", i);
            #define PRINT(type, ...) \
            clGetDeviceInfo(SL_devices[i][dev], type, 0, NULL, &info_len); /* get size */ \
            if (allocated < info_len) \
            { \
                allocated = info_len; \
                tmp = info; info = realloc(info, info_len); \
                if (!info) { free(tmp); return 57; }\
            } \
            clGetDeviceInfo(SL_devices[i][dev], type, info_len, info, NULL); /* get value */ \
            log(__VA_ARGS__, info)
            #define PRINV(type, typename, ...) \
            clGetDeviceInfo(SL_devices[i][dev], type, 0, NULL, &info_len); /* get size */ \
            if (allocated < info_len) \
            { \
                allocated = info_len; \
                tmp = info; info = realloc(info, info_len); \
                if (!info) { free(tmp); return 57; }\
            } \
            clGetDeviceInfo(SL_devices[i][dev], type, info_len, info, NULL); /* get value */ \
            log(__VA_ARGS__, *(typename *)info)
            #define PRINS(type, typename, ...) \
            clGetDeviceInfo(SL_devices[i][dev], type, 0, NULL, &info_len); /* get size */ \
            if (allocated < info_len) \
            { \
                allocated = info_len; \
                tmp = info; info = realloc(info, info_len); \
                if (!info) { free(tmp); return 57; }\
            } \
            clGetDeviceInfo(SL_devices[i][dev], type, info_len, info, NULL); /* get value */ \
            log(__VA_ARGS__, *(typename *)info) \
            dims = *(unsigned *)info;
            #define PRINI(type, typename, ...) \
            clGetDeviceInfo(SL_devices[i][dev], type, 0, NULL, &info_len); /* get size */ \
            if (allocated < info_len) \
            { \
                allocated = info_len; \
                tmp = info; info = realloc(info, info_len); \
                if (!info) { free(tmp); return 57; }\
            } \
            clGetDeviceInfo(SL_devices[i][dev], type, info_len, info, NULL); /* get value */ \
            for (int d = 0; d < dims; ++d) \
            { \
                log(__VA_ARGS__, d, ((typename *)info)[d]) \
            }
            PRINT(CL_DEVICE_NAME,                                     "\t%d.%d.Name                      : %s\n", i, dev)
            PRINV(CL_DEVICE_AVAILABLE, int,                           "\t%d.%d.Available                 : %x\n", i, dev)
            PRINV(CL_DEVICE_TYPE, unsigned,                           "\t%d.%d.Type                      : %x\n", i, dev)
            PRINT(CL_DEVICE_VENDOR,                                   "\t%d.%d.Vendor                    : %s\n", i, dev)
            PRINT(CL_DRIVER_VERSION,                                  "\t%d.%d.Driver Version            : %s\n", i, dev)
            PRINT(CL_DEVICE_VERSION,                                  "\t%d.%d.Device Version            : %s\n", i, dev)
            PRINT(CL_DEVICE_PROFILE,                                  "\t%d.%d.Profile                   : %s\n", i, dev)
            PRINT(CL_DEVICE_EXTENSIONS,                               "\t%d.%d.Extensions                : %s\n", i, dev)
            PRINV(CL_DEVICE_MAX_COMPUTE_UNITS, unsigned,              "\t%d.%d.Max Compute Units         : %u\n", i, dev)
            PRINS(CL_DEVICE_MAX_WORK_ITEM_DIMENSIONS, unsigned,       "\t%d.%d.Max Item Dimensions       : %u\n", i, dev)
            PRINV(CL_DEVICE_MAX_WORK_GROUP_SIZE, size_t,              "\t%d.%d.Max Group Size            : %zu\n", i, dev)
            PRINI(CL_DEVICE_MAX_WORK_ITEM_SIZES, size_t,              "\t\t%d.%d.Max Item Sizes[%d]        : %zu\n", i, dev)
            PRINV(CL_DEVICE_MAX_CLOCK_FREQUENCY, unsigned,            "\t%d.%d.Max Clock Frequency       : %u\n", i, dev)
            PRINV(CL_DEVICE_MAX_MEM_ALLOC_SIZE, unsigned long,        "\t%d.%d.Max Mem Alloc Size        : %lu\n", i, dev)
            PRINV(CL_DEVICE_GLOBAL_MEM_CACHELINE_SIZE, unsigned,      "\t%d.%d.Global Mem Cacheline Size : %u\n", i, dev)
            PRINV(CL_DEVICE_GLOBAL_MEM_CACHE_SIZE, unsigned long,     "\t%d.%d.Global Mem Cache Size     : %lu\n", i, dev)
            PRINV(CL_DEVICE_GLOBAL_MEM_SIZE, unsigned long,           "\t%d.%d.Global Mem Size           : %lu\n", i, dev)
            PRINV(CL_DEVICE_LOCAL_MEM_SIZE, unsigned long,            "\t%d.%d.Local Mem Size            : %lu\n", i, dev)
            #undef PRINT
            #undef PRINV
            #undef PRINS
            #undef PRINI
            free(info);
            putchar('\n');
        }
        count += read_count;
    }
    log("At end have %d devices.\n", count)
    return 0;
}

int SL_use_platform(int preferred_type)
{
    if (preferred_type == SL_PLATFORM_BEST)
    {
        return SL_best_platform;
    }
    return 0;
}

int SL_init_from_platform(int platform_id)
{
    int err;
    SL_context = clCreateContext(NULL,
                                 SL_devices_len[platform_id],
                                 SL_devices[platform_id],
                                 NULL, // using no function for errors detection
                                 NULL, // and no it's data
                                 &err);
    if (err) { return err; }
    return 0;
}

int SL_init_from_device(int platform_id, int device_id)
{
    int err;
    SL_context = clCreateContext(NULL,
                                 1,
                                 SL_devices[platform_id] + device_id,
                                 NULL, // using no function for errors detection
                                 NULL, // and no it's data
                                 &err);
    if (err) { return err; }
    return 0;
}

int SL_init_queues_on_platform(int platform_id)
{
    int err;
    for (int i = 0; i < SL_devices_len[platform_id]; ++i)
    {
        SL_queues[platform_id][i] = clCreateCommandQueueWithProperties(SL_context,
                                                         SL_devices[platform_id][i],
                                                         NULL,
                                                         &err);
        if (err) { return err; }
    }
    return 0;
}

int SL_init_queue_on_device(int platform_id, int device_id)
{
    int err;
    SL_queues[platform_id][device_id] = clCreateCommandQueueWithProperties(SL_context,
                                                              SL_devices[platform_id][device_id],
                                                              NULL,
                                                              &err);
    if (err) { return err; }
    return 0;
}

cl_kernel SL_compile_text(int platform_id, int device_id, const char *kernel_function_name, const char *source_code, size_t source_length, int *ret_err)
{
    int err;
    cl_program program = clCreateProgramWithSource(SL_context,
                                                   1,
                                                   &source_code,
                                                   &source_length,
                                                   &err);
    if (err) { if (ret_err) *ret_err = err; return NULL; }
    err = clBuildProgram(program,
                         0,
                         NULL, // SL_devices[platform_id] + device_id compile on all devices
                         // https://registry.khronos.org/OpenSL/specs/3.0-unified/html/OpenCL_API.html#compiler-options
                         "-cl-single-precision-constant -cl-unsafe-math-optimizations",
                         NULL,  // using no function for errors detection
                         NULL); // and no it's data

    if (err)
    {
        printf("BuildProgram Error: %d\n", err);
        size_t len = 0;
        cl_int ret = CL_SUCCESS;
        ret = clGetProgramBuildInfo(program, SL_devices[platform_id][device_id], CL_PROGRAM_BUILD_LOG, 0, NULL, &len);
        if (ret)
        {
            printf("BuildInfo Error: %d\n", ret);
            * ret_err = 1;
            return NULL;
        }
        len += 10;
        char *buffer = calloc(len, sizeof(char));
        ret = clGetProgramBuildInfo(program, SL_devices[platform_id][device_id], CL_PROGRAM_BUILD_LOG, len, buffer, NULL);
        if (ret)
        {
            printf("BuildInfo2 Error: %d\n", ret);
            * ret_err = 1;
            return NULL;
        }

        printf("Error Info: code=%d: info=%s\n", err, buffer);

        free(buffer);
        if (ret_err)
        {
            *ret_err = err;
        }
        return NULL;
    }
    cl_kernel kernel = clCreateKernel(program,
                                      kernel_function_name,
                                      &err);
    if (err) { if (ret_err) *ret_err = err; return NULL; }

    if (ret_err) *ret_err = 0;
    return kernel;
}

cl_kernel SL_compile_file(int platform_id, int device_id, const char *kernel_function_name, const char *filename, int *ret_err)
{
    int err;
    size_t content_length;
    char *content;
    int file_read_size;
    FILE *fp;

    fp = fopen(filename, "r");
    if(!fp) { if (ret_err) *ret_err = 179; return NULL; }

    fseek(fp, 0, SEEK_END);
    file_read_size = ftell(fp);
    rewind(fp);

    content = (char *)malloc(file_read_size);
    if (!content) { fclose(fp); if (ret_err) *ret_err = 257; return NULL; }
    content_length = fread(content, 1, file_read_size, fp);
    content[content_length] = 0;
    fclose(fp);

    cl_kernel kernel = SL_compile_text(0, 0, kernel_function_name, content, content_length, &err);
    if (err)
    {
        *ret_err = 1; return NULL;
    }

    free(content);
    if (ret_err) *ret_err = 0;
    return kernel;
}

cl_mem SL_alloc(size_t size, cl_mem_flags flags, int *ret_err)
{
    return clCreateBuffer(
                          SL_context,
                          flags,
                          size,
                          NULL,
                          ret_err);
}

cl_mem SL_share(size_t size, cl_mem_flags flags, void *host_ptr, int *ret_err)
{
    return clCreateBuffer(
                          SL_context,
                          flags,
                          size,
                          host_ptr,
                          ret_err);
}

int SL_run(int platform_id, int comand_queue_id, cl_kernel kernel, struct shape_t config_shape)
{
    return clEnqueueNDRangeKernel(SL_queues[platform_id][comand_queue_id],
                                  kernel,
                                  config_shape.dim,
                                  config_shape.global_offset,
                                  config_shape.global_size,
                                  NULL,
                                  0,
                                  NULL,
                                  NULL);
}

int SL_run_use_shape_local(int platform_id, int comand_queue_id, cl_kernel kernel, struct shape_t config_shape)
{
    return clEnqueueNDRangeKernel(SL_queues[platform_id][comand_queue_id],
                                  kernel,
                                  config_shape.dim,
                                  config_shape.global_offset,
                                  config_shape.global_size,
                                  config_shape.local_size,
                                  0,
                                  NULL,
                                  NULL);
}

int SL_finish_queues_on_platform(int platform_id)
{
    int err;
    for (int i = 0; i < SL_queues_len[platform_id]; ++i)
    {
        err = clFinish(SL_queues[platform_id][i]);
        if (err) { return err; }
    }
    return 0;
}

int SL_finish_queue(int platform_id, int device_id)
{
    return clFinish(SL_queues[platform_id][device_id]);
}
