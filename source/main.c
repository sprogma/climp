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

#include "main.h"



void DLL_EXPORT kernel(
    float *dst,
    int dst_len,
    // notes
    int *tools,
    float *times,
    float *lengths,
    float *freqs,
    float *volumes,
    int notes_len
)
{
    int err;
    struct track t;


    // init connection
    err = climp_connect();
    if (err)
    {
        fprintf(stderr, "Error in connection. Failed to connect device.");
        exit(1);
    }


    // load track
    err = climp_track_load(&t, dst, dst_len, tools, times, lengths, freqs, volumes, notes_len);
    if (err)
    {
        fprintf(stderr, "error at loading.\n");
        exit(1);
    }

    // process
    err = climp_track_process(&t);
    if (err)
    {
        fprintf(stderr, "error at processing.\n");
        exit(1);
    }

    err = climp_track_destroy(&t);
    if (err)
    {
        fprintf(stderr, "error at deallocating memory.\n");
        exit(1);
    }

    return;
}




DLL_EXPORT BOOL APIENTRY DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved)
{
    switch (fdwReason)
    {
        case DLL_PROCESS_ATTACH:
            // attach to process
            // return FALSE to fail DLL load
            break;

        case DLL_PROCESS_DETACH:
            // detach from process
            break;

        case DLL_THREAD_ATTACH:
            // attach to thread
            break;

        case DLL_THREAD_DETACH:
            // detach from thread
            break;
    }
    return TRUE; // succesful
}

/*int main()
{
    int err;
    err = climp_connect();

    float t[2] = {0.0};
    float l[2] = {0.001};
    float f[2] = {440.0};
    float v[2] = {1.0};
    float x[2000];
    kernel(x, 1000, t, l, f, v, 1);

    if (err) { fprintf(stderr, "Error in connection. Failed to load DLL."); return FALSE; }
    return 0;
}*/
