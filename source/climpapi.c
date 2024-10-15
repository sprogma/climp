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



/*
    Loads track into first operand, using passed data
*/
int climp_load_track(
    struct track *t,
    struct instrument *instruments;
    size_t instruments_len,
    float *dst,
    size_t dst_len,
    struct input_note *notes,
    size_t notes_len,
    float base_freq)
{
    /// fill raw result buffer
    t->samples = dst_len;
    t->buffer = dst;

    /// fill instruments data
    t->instruments_len = instruments_len;
    t->instruments = instruments;

    /// copy and convert notes input
    t->notes_len = notes_len;
    struct note *notes_copy = malloc(sizeof(*notes_copy) * t->notes_len);
    if (!notes_copy) {return 1;} // test malloc error
    // copy data
    memcpy(notes_copy, notes, sizeof(*notes_copy) * t->notes_len);
    // save pointer
    t->notes = notes_copy;
    // convert input_note to note
    /*may be this convertion will be needed in future*/

    /// allocate beats buffer
    t->beat_samples = output_frequency / BEATS_PER_SECOND;
    t->beats_len = (t->samples + t->beat_samples - 1) / t->beat_samples;
    t->beats = malloc(sizeof(*t->beats) * t->beats_len);
    if (!t->beats) {free(t->notes); return 1;} // test malloc error
    // fill by -1 - end terminating values
    memset(t->beats, 0xFF, sizeof(*t->beats) * t->beats_len);

    return 0;
}

/**
    Calculate beats buffer:
        beats[time_step] -> array of notes (their ids),
                            which intersect with this time_step
**/
int climp_track_generate_beats(struct track *t)
{
    // for each note
    for (int note_id = 0; note_id < t->notes_len; ++note_id)
    {
        // get boundaries, there note sounds
        int l = t->notes[i].time_start / t->beat_samples;
        int r = t->notes[i].time_end / t->beat_samples;
        for (int beat = l; beat <= r; ++beat)
        {
            int k = 0; // position in beat cell to insert note id.
            // inefficient insert, but efficient read.
            while (t->beats[beat][k] != -1 && k < NOTES_PER_BEAT) {k++;}
            // raise error if buffer size is exceeded
            if (k == NOTES_PER_BEAT)
            {
                fprintf(stderr, "Error: count of notes in one beat has exceeded value NOTES_PER_BEAT=%d.\n"
                                "Simplify your track, use more complicated instruments, or increase NOTES_PER_BEAT value.\n", NOTES_PER_BEAT);
                return 1;
            }
            // append note to this beat
            t->beats[beat][k] = note_id;
        }
    }
    return 0;
}

/*
    Prepares track - generates kernels for each instrument, and final code.
*/
int climp_track_generate_kernel(struct track *t)
{
    /// allocate kernel buffer
    char *result_kernel = malloc(MAX_KERNEL_SIZE);
    char *instruments_source_buffer = malloc(MAX_KERNEL_SIZE);
    char *instruments_branching_buffer = malloc(MAX_KERNEL_SIZE);
    int result_kernel_len = 0;
    int instruments_source_buffer_len = 0;

    // check for allocation error
    // and free least values
    if (!result_kernel) {return 1; free(instruments_source_buffer); free(instruments_branching_buffer)}
    if (!instruments_source_buffer) {return 1; free(instruments_branching_buffer); free(result_kernel)}
    if (!instruments_branching_buffer) {return 1; free(instruments_source_buffer); free(result_kernel)}


    /// load base of kernel
    FILE *source_file = fopen("./kernel.cl", "r");
    if (!source_file) {return 2;} // check for error
    // read source, and save it's len
    result_kernel_len = fread(result_kernel, 1, result_kernel, source_file);
    fclose(source_file);

    /// init all instruments

    // insert each instruments' source code into kernel

    for (int instrument_id = 0; instrument_id < t->instruments_len; ++instrument_id)
    {
        // copy next kernel source, and adjust buffer len after addition.
        memcpy(instruments_source_buffer + instruments_source_buffer_len, t->instruments[instrument_id].kernel_source, t->instruments[instrument_id].kernel_source_len);
        instruments_source_buffer_len += t->instruments[instrument_id].kernel_source_len;
    }

    // insert each instrument into call branching

    for (int instrument_id = 0; instrument_id < t->instruments_len; ++instrument_id)
    {
        sprintf(, " if (note->) {} else ")
    }

    /// search for string position
    // this is standard placeholder
    // it will be replaced in kernel on instruments sources
    const char source_placeholder[] = "INSTRUMENTS_SOURCE_LINE";
    const int source_placeholder_length = sizeof(source_placeholder) - 1;
    // find position of placeholder in kernel source
    int position = 0;
    while (position < result_kernel_len - source_placeholder_length &&
           strncmp(result_kernel + position, source_placeholder, source_placeholder_length) != 0)
    {
        position++;
    }
    // if not found default placeholder, raise error.
    if (position == result_kernel_len - source_placeholder_length)
    {
        fprintf(stderr, "Kernel code corrupted. Not found label <%s>", source_placeholder);
        return 2;
    }


    /// replace default placeholder with instruments_buffer data


    return 0;
}


int climp_process_track()
{

}
