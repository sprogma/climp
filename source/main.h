#ifndef __MAIN_H__
#define __MAIN_H__

#include <windows.h>

/*  To use this exported function of dll, include this header
 *  in your project.
 */

#ifdef BUILD_DLL
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT __declspec(dllimport)
#endif


#ifdef __cplusplus
extern "C"
{
#endif


/*
    structure with input notes data
*/
struct input_note
{
    int instrument;
    float frequency;
    float time;
    float length;
    char data[32];
};

/**
    structure with input instrument data:
    @attribute kernel_soure - this is string, containing code of kernel
                              which will calculate result for this instrument
                              (and kernel_source_len - it's length)

    @attribute kernel_name  - this is string, containing name of main kernel
                              function to call (this string will be placed in
                              code which will call this instrument)

**/
struct instrument
{
    char *kernel_source;
    int kernel_source_len;
    char *kernel_name;
};

/*
    Main export function:

    takes on input three arrays -
        destination buffer
        instruments
        notes
    and some extra configure parameters
        base_frequency
*/
void DLL_EXPORT kernel(
    struct instrument *instruments;
    size_t instruments_len,
    float *dst,
    size_t dst_len,
    struct input_note *notes,
    size_t notes_len,
    float base_freq
);

#ifdef __cplusplus
}
#endif

#endif // __MAIN_H__
