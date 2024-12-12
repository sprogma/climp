#ifndef CLIMPAPI_H_INCLUDED
#define CLIMPAPI_H_INCLUDED


#define PARALLEL_CHANELS 2048
#define NOTE_SIZE 32


struct __attribute__ ((packed)) note
{
    int tool;
    int start;
    int end;
    float freq;
    float volume;
};


struct track
{
    // information
    int freq; // samples on beat
    float freqf; // Hz
    int samples;
    float samplesf;
    // arrays
    struct note *notes;
    int notes_len;
    // samples destination
    float *dest;

    // optimizing array
    int (*opt)[PARALLEL_CHANELS];
    int opt_beat_samples;
    int opt_len;
};






int climp_connect();

int climp_track_load(struct track *t, float *dst, int dst_len, int *tools, float *times, float *lengths, float *freqs, float *volumes, int notes_len);

int climp_track_process(struct track *t);

int climp_track_destroy(struct track *t);


#endif // CLIMPAPI_H_INCLUDED
