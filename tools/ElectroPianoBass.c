
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
    float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
    v *= fmax(0.01f, k);
    
    float res = 0.0, dr;
    for (int fqid = 0; fqid < sizeof(freq) / sizeof(*freq); ++fqid)
    {
        float f = note->frequency * (fqid + 1) * 0.25;
        float fv = freq[fqid];
        dr = sin(s * f / 44100.0f * 0.5 * 3.1415926 * 2.0);
        res += fv*v*dr;
    }
    return res;
