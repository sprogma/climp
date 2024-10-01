#ifndef CLIMPAPI_H_INCLUDED
#define CLIMPAPI_H_INCLUDED


#define NOTES_PER_BEAT 512


enum
{
    NOTEMODE_LINEAR=0,
    NOTEMODE_FAST=1,
};


struct note
{
    int sample[2];
    float freq[2];
    float volume[2];
};

struct note_meta
{
    int tool;
};

struct tool
{

};

struct track
{
    /* meta info */
    int freq;
    float ffreq;
    int beat_time;
    int time;

    /* arrays */
    float *raw; // length of raw is time.

    struct tool *tools;

    struct note_meta *notes_meta;
    struct note *notes;
    int *modes;
    int notes_len;

    int (*beats)[NOTES_PER_BEAT];
    int beats_len;
};


int climp_load_track(struct track *t, float *dst, size_t dst_len, float *notes,
                      int *tools, int *modes, size_t notes_len, int base_freq);

int climp_process_track_software(struct track *t);


#endif // CLIMPAPI_H_INCLUDED
