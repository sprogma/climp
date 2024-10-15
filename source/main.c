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
    struct instrument *instruments;
    size_t instruments_len,
    float *dst,
    size_t dst_len,
    struct input_note *notes,
    size_t notes_len,
    float base_freq
)
{

    struct track t;
    climp_load_track(&t, dst, dst_len, notes, notes_len, base_freq);


    climp_process_track_software(&t);

    fflush(stdout);
    fflush(stderr);

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
