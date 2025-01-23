
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

float Horn(float s, struct note *note, float rnd){ 
    float freq[] = {
        0.6,
        0.5,
        0.3,
        0.3,
        0.1,
        0.0025,
        0.001
    };

    float v = note->volume;
    float x = (float)(s - note->start) / 44100.0f;
    float l = (float)(note->end - note->start) / 44100.0f;
    float k = tanh(20.0*x) * cos(x * 3.1415926 * 0.5 / l);
    v *= k;
    
    float res = 0.0, dr;
    for (int fqid = 0; fqid < sizeof(freq) / sizeof(*freq); ++fqid)
    {
            float f = note->frequency * (fqid + 1);
        float fv = freq[fqid];
        dr = sin(s * f / 44100.0f * 0.5 * 3.1415926 * 2.0);
        res += fv*v*dr;
    }
    return res;
 }

float PianoSolo(float s, struct note *note, float rnd){ 
    float freq[] = {
        0.5,
        0.9,
        0.1,
        0.1,
        0.1,
        0.0025,
        0.001
    };

    float v = note->volume;
    float x = (float)(s - note->start) / 44100.0f;
    float l = (float)(note->end - note->start) / 44100.0f;
    float k = tanh(20.0*x) * cos(x * 3.1415926 * 0.5 / l);
    v *= k;
    
    float res = 0.0, dr;
    for (int fqid = 0; fqid < sizeof(freq) / sizeof(*freq); ++fqid)
    {
            float f = note->frequency * (fqid + 1);
        float fv = freq[fqid];
        dr = sin(s * f / 44100.0f * 0.5 * 3.1415926 * 2.0);
        res += fv*v*dr;
    }
    return res;
 }

float PianoAlto(float s, struct note *note, float rnd){ 
    float freq[] = {
        0.2,
        0.5,
        0.05,
        1.0,
        0.05,
        0.025,
        0.0125,
        0.3
    };
    float v = note->volume;
    float x = (float)(s - note->start) / 44100.0f;
    float l = (float)(note->end - note->start) / 44100.0f;
    float k = tanh(20.0*x) * cos(x * 3.1415926 * 0.5 / l);
    v *= k;
    
    float res = 0.0, dr;
    for (int fqid = 0; fqid < sizeof(freq) / sizeof(*freq); ++fqid)
    {
        float f = note->frequency * (fqid + 1) * 0.25;
        float fv = freq[fqid];
        dr = sin(s * f / 44100.0f * 0.5 * 3.1415926 * 2.0);
        res += fv*v*dr;
    }
    return res;
 }

float PianoBass(float s, struct note *note, float rnd){ 

    float freq[] = {
        0.2,
        0.3,
        0.05,
        0.9,
        0.05,
        0.25,
        0.15,
        0.5,
        0.015,
        0.005,
        0.015,
        0.6,
        0.015,
        0.005,
        0.015,
        0.4,
    };

    float v = note->volume;
    float x = (float)(s - note->start) / 44100.0f;
    float l = (float)(note->end - note->start) / 44100.0f;
    float k = tanh(200.0*x) * cos(x * 3.1415926 * 0.5 / l);
    v *= k;

    float res = 0.0, dr;
    for (int fqid = 0; fqid < sizeof(freq) / sizeof(*freq); ++fqid)
    {
        float f = note->frequency * (fqid + 1) * 0.25;
        float fv = freq[fqid] * 0.5;
        dr = sin(s * f / 44100.0f * 0.5 * 3.1415926 * 2.0);
        res += fv*v*dr;
    }
    return res;
 }

float Drum(float s, struct note *note, float rnd){ 
    float dr;
    float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
    v *= fmax(0.01f, k);
    return v * rnd;
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
            case 0: res += Horn(s, notes + n, rnd); break;
case 1: res += PianoSolo(s, notes + n, rnd); break;
case 2: res += PianoAlto(s, notes + n, rnd); break;
case 3: res += PianoBass(s, notes + n, rnd); break;
case 4: res += Drum(s, notes + n, rnd); break;

            default:
                break;
            }
        }
        note++;
    }

    dest[s] = res;
    return;
}
