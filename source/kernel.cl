
#define PARALLEL_CHANELS 2048

struct __attribute__ ((packed)) note
{
    int start;
    int end;
    float frequency;
    float volume;
};

kernel void generation_kernel( __global float *dest,
                               uint dst_len,
                               __global struct note *notes,
                               uint notes_len,
                               __global int *opt,
                               uint opt_beat_samples,
                               uint opt_len
)
{
    int s = get_global_id(0);

    float res = 0.0;
    float dr;

    // iterate from notes
    int beat = s / opt_beat_samples;
    int note = 0, n;
    while ((n = opt[beat * PARALLEL_CHANELS + note]) != -1)
    {
        if (notes[n].start <= s && s <= notes[n].end)
        {
            float v = notes[n].volume, k = 1.0f - (float)(s - notes[n].start) / 44100.0f;//(float)(notes[n].end - notes[n].start);
            v *= fmax(0.01f, k);
            dr = sin(s * notes[n].frequency / 44100.0f * 3.1415926f); // *= 2.0f ?
            res += v*(smoothstep(-0.3, 0.3, dr)*2.0-1.0);
        }
        note++;
    }

    dest[s] = res;
    return;
}
