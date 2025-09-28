
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

float wave(float time) {
    return sin(time * 3.1415926f * 2.0f);
}

float saw(float time) {
    float _;
    float x = fract(time, &_);
    return fabs(x * 2.0f - 1.0f) * 2.0f - 1.0f;
}

float PianoLeg(float s, struct note *note, float rnd){ 
    float v = note->volume;
    float x = (float)(s - note->start) / 44100.0f;
    float l = (float)(note->end - note->start) / 44100.0f;
    float k = tanh(1000.0*x) * cos(x * 3.1415926 * 0.5 / l);
    v *= k;
    
    float res = 0.0, dr;
    {
        dr = wave(s * note->frequency / 44100.0f);
        res += dr * 0.66;
        dr = wave(s * note->frequency / 44100.0f * 0.5);
        res += dr * 0.33;
    }
    return res * v;
 }

float PianoSolo(float s, struct note *note, float rnd){ 
    float v = note->volume;
    float x = (float)(s - note->start) / 44100.0f;
    float l = (float)(note->end - note->start) / 44100.0f;
    float k = tanh(1000.0*x) * cos(x * 3.1415926 * 0.5 / l);
    v *= k;
    
    float res = 0.0, dr;
    {
        dr = wave(s * note->frequency / 44100.0f);
        res += dr * 0.66;
        dr = wave(s * note->frequency / 44100.0f * 0.5);
        res += dr * 0.33;
    }
    return res * v;
 }

float SawSolo(float s, struct note *note, float rnd){ 
    float v = note->volume;
    float x = (float)(s - note->start) / 44100.0f;
    float l = (float)(note->end - note->start) / 44100.0f;
    float k = tanh(1000.0*x) * cos(x * 3.1415926 * 0.5 / l);
    v *= k;

    float res = 0.0, dr;
    {
        dr = saw(s * note->frequency / 44100.0f);
        dr = dr * dr * dr;
        res += dr * 0.66;
        dr = saw(s * note->frequency / 44100.0f * 0.5);
        dr = dr * dr * dr;
        res += dr * 0.33;
    }
    return res * v;
 }

float PSolo(float s, struct note *note, float rnd){ 
    float v = note->volume;
    float x = (float)(s - note->start) / 44100.0f;
    float l = (float)(note->end - note->start) / 44100.0f;
    float k = tanh(1000.0*x) * cos(x * 3.1415926 * 0.5 / l);
    v *= k;

    float dr;
    {
        dr = clamp(wave(s * note->frequency / 44100.0f) * 20.0, -1.0, 1.0);
    }
    return v*dr;
 }

float WaveSaw(float s, struct note *note, float rnd){ 
    float v = note->volume;
    float x = (float)(s - note->start) / 44100.0f;
    float l = (float)(note->end - note->start) / 44100.0f;
    float k = tanh(1000.0*x) * cos(x * 3.1415926 * 0.5 / l);
    v *= k;

    float res = 0.0, dr;
    {
        float x;
        x = s * note->frequency / 44100.0f;
        dr = wave(x) * saw(x) * saw(x) * 4.488;
        res += dr * 0.66;
        x = s * note->frequency / 44100.0f * 0.5;
        dr = wave(x) * saw(x) * saw(x) * 4.488;
        res += dr * 0.33;
    }
    return res * v;
 }

float PianoBass(float s, struct note *note, float rnd){ 
    float v = note->volume;
    float x = (float)(s - note->start) / 44100.0f;
    float l = (float)(note->end - note->start) / 44100.0f;
    float k = tanh(1000.0*x) * cos(x * 3.1415926 * 0.5 / l);
    v *= k;

    float res = 0.0, dr;
    {
        dr = wave(s * note->frequency / 44100.0f);
        res += dr * 0.66;
        dr = wave(s * note->frequency / 44100.0f * 0.5);
        res += dr * 0.33;
    }
    return res * v;
 }

float SawBass(float s, struct note *note, float rnd){ 
    float v = note->volume;
    float x = (float)(s - note->start) / 44100.0f;
    float l = (float)(note->end - note->start) / 44100.0f;
    float k = tanh(1000.0*x) * cos(x * 3.1415926 * 0.5 / l);
    v *= k;

    float res = 0.0, dr;
    {
        dr = saw(s * note->frequency / 44100.0f);
        res += dr * 0.66;
        dr = saw(s * note->frequency / 44100.0f * 0.5);
        res += dr * 0.33;
    }
    return res * v;
 }

float PBass(float s, struct note *note, float rnd){ 
    float v = note->volume;
    float x = (float)(s - note->start) / 44100.0f;
    float l = (float)(note->end - note->start) / 44100.0f;
    float k = tanh(1000.0*x) * cos(x * 3.1415926 * 0.5 / l);
    v *= k;

    float dr;
    {
        dr = clamp(wave(s * note->frequency / 44100.0f) * 20.0, -1.0, 1.0);
    }
    return v*dr;
 }

float Bass(float s, struct note *note, float rnd){ 
    float v = note->volume;
    float x = (float)(s - note->start) / 44100.0f;
    float l = (float)(note->end - note->start) / 44100.0f;
    float k = tanh(1000.0*x) * cos(x * 3.1415926 * 0.5 / l);
    v *= k;

    float dr;
    {
        dr = wave(s * note->frequency / 44100.0f);
    }
    return v*dr * 2.0;
 }

float Drum(float s, struct note *note, float rnd){ 
    /* check type of note -> select drum type */
    if (fabs(note->frequency - 440.0 / 4) < 0.1)
    {    
        float dr;
        float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
        v *= fmax(0.01f, k);
        return v * rnd;
    }
    else if (fabs(note->frequency - 440.0 / 2) < 0.1)
    {
        float dr;
        float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
        v *= fmax(0.01f, k);
        s = floor(s / 4.0);
        return 1.15 * v * (random(s / 44100.0) * 2.0 - 1.0);
    }
    else if (fabs(note->frequency - 440.0 / 1) < 0.1)
    {
        float dr;
        float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
        v *= fmax(0.01f, k);
        s = floor(s / 16.0);
        return 1.3 * v * (random(s / 44100.0) * 2.0 - 1.0);
    }
    else if (fabs(note->frequency - 440.0 * 2.0) < 0.1)
    {
        float dr;
        float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
        v *= fmax(0.01f, k);
        s = floor(s / 32.0);
        return 1.3 * v * (random(s / 44100.0) * 2.0 - 1.0);
    }
    return 0;
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
            case 0: res += PianoLeg(s, notes + n, rnd); break;
case 1: res += PianoSolo(s, notes + n, rnd); break;
case 2: res += SawSolo(s, notes + n, rnd); break;
case 3: res += PSolo(s, notes + n, rnd); break;
case 4: res += WaveSaw(s, notes + n, rnd); break;
case 5: res += PianoBass(s, notes + n, rnd); break;
case 6: res += SawBass(s, notes + n, rnd); break;
case 7: res += PBass(s, notes + n, rnd); break;
case 8: res += Bass(s, notes + n, rnd); break;
case 9: res += Drum(s, notes + n, rnd); break;

            default:
                break;
            }
        }
        note++;
    }

    dest[s] = res;
    return;
}
