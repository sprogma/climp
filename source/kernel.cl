
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

float PianoSolo(float s, struct note *note, float rnd){ 
    float dr;
    //float v = note->volume, k = 1.0f - (float)(s - note->start) / 44100.0f;//(float)(note->end - note->start);
    float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
    v *= fmax(0.01f, k);
    dr = sin(s * note->frequency / 44100.0f * 0.5 * 3.1415926 * 2.0);
    return v*(smoothstep(-0.3, 0.3, dr)*2.0-1.0);
 }

float PianoBass(float s, struct note *note, float rnd){ 
    float dr;
    //float v = note->volume, k = 1.0f - (float)(s - note->start) / 44100.0f;//(float)(note->end - note->start);
    float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
    v *= fmax(0.01f, k);
    dr = sin(s * note->frequency / 44100.0f * 0.5 * 3.1415926 * 2.0);
    return v*(smoothstep(-0.3, 0.3, dr)*2.0-1.0);
 }

float Dram(float s, struct note *note, float rnd){ 
    float dr;
    float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
    v *= fmax(0.01f, k);
    return v * rnd;
 }

float aboba(float s, struct note *note, float rnd){ 
    /*Enter code here to generate sample 's' from note 'note' (rnd is white noise from -1 to 1)*/
    float dr;
    float v = note->volume;
    float k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
    v *= fmax(0.01f, k);
    dr = sin(s * note->frequency / 44100.0f * 3.1415926);
    return v*dr;
 }



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
            case 0: res += PianoSolo(s, notes + n, rnd); break;
case 1: res += PianoBass(s, notes + n, rnd); break;
case 2: res += Dram(s, notes + n, rnd); break;
case 3: res += aboba(s, notes + n, rnd); break;

            default:
                break;
            }
        }
        note++;
    }

    dest[s] = res;
    return;
}
