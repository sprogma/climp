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

void DLL_EXPORT kernel(
    float *dst,
    size_t dst_len,
    float *notes,
    int   *tools,
    int   *modes,
    size_t notes_len,
    int    base_freq
);

#ifdef __cplusplus
}
#endif

#endif // __MAIN_H__
