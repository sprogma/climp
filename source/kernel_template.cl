
#define PARALLEL_CHANELS 2048

struct __attribute__ ((packed)) note
{
    int tool;
    int start;
    int end;
    float frequency;
    float volume;
};


float random(float time) {
    float _;
    return fract(sin(time * 78.233) * 43758.5453123, &_);
}

<TOOLS_FUNCTION>

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

    float rnd = random(100.0 * s / (float)dst_len) * 2.0 - 1.0;
    //printf("%f\n", rnd);

    float res = 0.0;

    // iterate from notes
    int beat = s / opt_beat_samples;
    int note = 0, n;
    while ((n = opt[beat * PARALLEL_CHANELS + note]) != -1)
    {
        if (notes[n].start <= s && s <= notes[n].end)
        {
            switch (notes[n].tool)
            {
            <TOOLS_SWITCH>
            default:
                break;
            }
        }
        note++;
    }

    dest[s] = res;
    return;
}
