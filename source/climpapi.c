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




int climp_load_track(struct track *t, float *dst, size_t dst_len, float *notes,
                      int *tools, int *modes, size_t notes_len, int base_freq)
{
    // fill meta data

    t->time  = dst_len;           // load samples count.
    t->freq  = base_freq;         // load freq.
    t->ffreq = base_freq;         // load freq.
    t->beat_time = t->freq / 10; // 10 beats per second.

    t->beats_len = t->time / t->beat_time + 1;
    t->notes_len = notes_len;

    // bind memory buffers

    t->raw = dst;           // use given pointer
    t->notes = notes;       // use given pointer
    t->notes_meta = tools;  // use given pointer
    t->beats = malloc(sizeof(*t->beats) * t->beats_len);

    // fill buffers

    memset(t->beats, 0xFF, sizeof(*t->beats) * t->beats_len); // fill beats with -1.
    for (int i = 0; i < t->notes_len; ++i)
    {
        t->notes[i].sample[0] = notes[6 * i + 0] * base_freq;
        t->notes[i].sample[1] = notes[6 * i + 1] * base_freq;
    }

    // calculate buffers
    {
        for (int i = 0; i < t->notes_len; ++i)
        {
            int l = t->notes[i].sample[0];
            int r = t->notes[i].sample[1];
            // apply to all buffers
            int bl = l / t->beat_time;
            int br = r / t->beat_time;
            for (int b = bl; b <= br; ++b)
            {
                int k = 0;
                while (t->beats[b][k] != -1 && k < NOTES_PER_BEAT) { k++; } // get end of non -1 data
                if (k == NOTES_PER_BEAT)
                {
                    fprintf(stderr, "Error: too many notes in one beat.\n");
                    return 1;
                }
                t->beats[b][k] = i;
            }
        }
    }

    // return
    return 0;
}


int climp_process_track_software(struct track *t)
{
    // for each sample: generate sound.
    for (int i = 0; i < t->time; ++i)
    {
        float value = 0.0;

        int note, k = 0, bt = i / t->beat_time;
        while ((note = t->beats[bt][k++]) != -1)
        {
            // get shift
            float start = (float)((i - t->notes[note].sample[0]) / (float)(t->notes[note].sample[1] - t->notes[note].sample[0]));
            if (0.f <= start && start <= 1.f)
            {
                // add note
                float v = t->notes[note].volume[0] * (1.0f - start) + start * t->notes[note].volume[1];
                float f = t->notes[note].freq[0] * (1.0f - start) + start * t->notes[note].freq[1];

                value += v * sin((float)i * f / t->ffreq * 2.0f * (float)M_PI);
            }
        }

        t->raw[i] = value;
    }

    return 0;
}
