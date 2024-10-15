#ifndef CLIMPAPI_H_INCLUDED
#define CLIMPAPI_H_INCLUDED


#define BEATS_PER_SECOND 10.0f
#define NOTES_PER_BEAT 512
#define MAX_KERNEL_SIZE 32768


/*
    struct note may has fields start and end - filled with samples of
    time and time + length values from struct input_note
*/
struct note
{
    int instrument;
    float frequency;
    float time;
    float length;
    char data[32];
};


struct track
{
    /* meta info */
    float freq;

    /* data storages */

    float *buffer; // raw result
    int samples;

    struct instrument *instruments; // instruments data
    int instruments_len;

    struct note *notes; // input notes
    int notes_len;

    /*
        beats buffer:
            beats[time_step] -> -1 terminating array of notes (their ids),
                                which intersect with this time_step

            time_step * beat_samples = samples of note

            beats_len * beat_samples >= samples
    */
    int beat_samples;
    int (*beats)[NOTES_PER_BEAT]; // optimizing information about notes.
    int beats_len;
};


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
    float base_freq);


/*
    Prepares track - generates kernels, calculating
    beats buffers, doing other stuff.
*/
int climp_track_generate_beats(struct track *t);
/*
    Prepares track - generates kernels, calculating
    beats buffers, doing other stuff.
*/
int climp_track_generate_kernel(struct track *t);


#endif // CLIMPAPI_H_INCLUDED
