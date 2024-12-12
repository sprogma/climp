#include "string.h"
#include "inttypes.h"
#include "stdio.h"
#include "stdlib.h"
#include "stdalign.h"
#include "stdarg.h"
#include "math.h"

#include "CL/cl.h"
#include "climpapi.h"
#include "gpgpu.h"



int UsedPlatform = -1;
int UsedDevice = -1;



int climp_track_generate_beats(struct track *t);
int climp_track_process_C(struct track *t);



int climp_connect()
{
    if (UsedPlatform != -1)
    {
        return 0;
    }
    int err;
    err = SL_init(CL_DEVICE_TYPE_ALL); fflush(stdout);
    UsedPlatform = SL_use_platform(SL_PLATFORM_BEST);
    UsedDevice = 0;
    if (err){ fprintf(stderr, "error when trying to establish connection"); return err; }
    err = SL_init_from_platform(UsedPlatform);
    if (err){ fprintf(stderr, "error when trying to initialize platform"); return err; }
    err = SL_init_queues_on_platform(UsedPlatform);
    if (err){ fprintf(stderr, "error when trying to initialize device"); return err; }
    return 0;
}



int climp_track_load(struct track *t, float *dst, int dst_len, int *tools, float *times, float *lengths, float *freqs, float *volumes, int notes_len)
{
    // fill structure
    t->dest = dst;
    t->opt_beat_samples = 44100 / 10;
    t->samples = dst_len;
    t->samplesf = (float)dst_len;
    t->freqf = 44100.0f;
    t->freq = 44100; // samples per second
    t->notes_len = notes_len;
    t->notes = malloc(sizeof(*t->notes) * t->notes_len);
    t->opt_len = 1 + t->samples / t->opt_beat_samples;
    t->opt = malloc(sizeof(*t->opt) * t->opt_len);
    memset(t->opt, 0xFF, sizeof(*t->opt) * t->opt_len);

    // load notes
    for (int id = 0; id < notes_len; ++id)
    {
        t->notes[id].tool  = tools[id];
        t->notes[id].start  = (int)(t->freqf * times[id]);
        t->notes[id].end    = (int)(t->freqf * (times[id] + lengths[id]));
        t->notes[id].freq   = freqs[id];
        t->notes[id].volume = volumes[id];
    }


    climp_track_generate_beats(t);


    return 0;
}


/**
    Calculate beats buffer:
        opt[time_step] -> array of notes (their ids),
                          which intersect with this time_step
**/
int climp_track_generate_beats(struct track *t)
{
    // for each note
    for (int note_id = 0; note_id < t->notes_len; ++note_id)
    {
        // get boundaries, there note sounds
        int l = t->notes[note_id].start / t->opt_beat_samples;
        int r = t->notes[note_id].end / t->opt_beat_samples;
        for (int beat = l; beat <= r; ++beat)
        {
            int k = 0; // position in beat cell to insert note id.
            // inefficient insert, but efficient read.
            while (t->opt[beat][k] != -1 && k+1 < PARALLEL_CHANELS) {k++;}
            // raise error if buffer size is exceeded
            if (k == PARALLEL_CHANELS)
            {
                fprintf(stderr, "Error: count of notes in one beat has exceeded value PARALLEL_CHANELS=%d.\n"
                                "Simplify your track, use more complicated instruments, or increase PARALLEL_CHANELS value.\n", PARALLEL_CHANELS-1);
                return 1;
            }
            // append note to this beat
            t->opt[beat][k] = note_id;
        }
    }
    return 0;
}


int climp_track_process(struct track *t)
{
    int err;

    // compile kernel
    cl_kernel kernel = SL_compile_file(UsedPlatform, UsedDevice, "generation_kernel", "D:/C/git/climp/source/kernel.cl", &err);
    if (err) { fprintf(stderr, "kernel compilation failed.\n"); return err;}

    // allocate memory
    cl_mem dest = SL_alloc(t->samples * sizeof(cl_float), 0, &err);
    if (err) { fprintf(stderr, "memory allocation failed. %d\n", err); return err;}
    cl_mem notes = SL_alloc(t->notes_len * sizeof(*t->notes), CL_MEM_READ_ONLY, &err);
    if (err) { fprintf(stderr, "memory allocation failed. %d\n", err); return err;}
    cl_mem opt = SL_alloc(t->opt_len * sizeof(*t->opt), CL_MEM_READ_ONLY, &err);
    if (err) { fprintf(stderr, "memory allocation failed. %d\n", err); return err;}

    // load buffers
    err = clEnqueueWriteBuffer( SL_queues[UsedPlatform][UsedDevice],
                          notes,
                          CL_TRUE,
                          0,
                          sizeof(*t->notes) * t->notes_len,
                          t->notes,
                          0, NULL, NULL );
    clEnqueueWriteBuffer( SL_queues[UsedPlatform][UsedDevice],
                          opt,
                          CL_TRUE,
                          0,
                          sizeof(*t->opt) * t->opt_len,
                          t->opt,
                          0, NULL, NULL );

    // set args
    clSetKernelArg(kernel, 0, sizeof(dest), (void*) &dest);
    clSetKernelArg(kernel, 1, sizeof(t->samples), (void*) &t->samples);
    clSetKernelArg(kernel, 2, sizeof(notes), (void*) &notes);
    clSetKernelArg(kernel, 3, sizeof(t->notes_len), (void*) &t->notes_len);
    clSetKernelArg(kernel, 4, sizeof(opt), (void*) &opt);
    clSetKernelArg(kernel, 5, sizeof(t->opt_beat_samples), (void*) &t->opt_beat_samples);
    clSetKernelArg(kernel, 6, sizeof(t->opt_len), (void*) &t->opt_len);

    struct shape_t shape = {};
    shape.dim = 1;
    shape.global_offset[0] = 0;
    shape.global_size[0] = t->samples;

    printf("Start [total_size=%dk]...\n", t->samples/1000);fflush(stdout);
    err = SL_run(UsedPlatform, UsedDevice, kernel, shape);
    if (err) { fprintf(stderr, "error at run of kernel. %d\n", err); return err; }
    SL_finish_queues_on_platform(UsedPlatform);


    cl_float *ptr;
    ptr = (cl_float *) clEnqueueMapBuffer( SL_queues[UsedPlatform][UsedDevice],
                                          dest,
                                          CL_TRUE,
                                          CL_MAP_READ,
                                          0,
                                          t->samples * sizeof(cl_float),
                                          0, NULL, NULL, NULL );
    printf("End...\n");fflush(stdout);


    memcpy(t->dest, ptr, sizeof(*t->dest) * t->samples);

    clEnqueueUnmapMemObject(SL_queues[UsedPlatform][UsedDevice],
                            dest,
                            ptr,
                            0, NULL, NULL);
    clReleaseMemObject(dest);
    clReleaseMemObject(notes);
    clReleaseMemObject(opt);

    return 0;
}


int climp_track_destroy(struct track *t)
{
    free(t->notes);
    free(t->opt);
    return 0;
}

