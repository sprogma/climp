

struct note
{
    int instrument_id;
    float frequency;
    float time;
    float length;
    char data[32];
}


/* placeholder for instruments */
INSTRUMENTS_SOURCE_LINE

float default_instrument(float sample_time, struct note *note, float base_frequency)
{
    return sin(note->frequency / base_frequency);
}



kernel void generation_kernel(  float *dst,
                                uint dst_len,
                                struct note *notes,
                                uint notes_len,
                                float *beats,
                                uint beats_len,
                                uint beats_samples,
                                float base_frequency
)
{
    /* move points */
    int id = get_global_id(0);
    float sample_time = (float)id / base_frequency;

    /* for each note in this beat,  */
    /* apply it's instrument kernel */

    int note_id;
    int beat = 32 * id / beats_samples;
    float global_result = 0.0, result;
    struct note *note;

    while ((note_id = beats[beat]) != -1)
    {
        note = notes + note_id;
        /* update this note */
        INSTRUMENTS_BRANCHING_LINE
        else
        {
            result = default_instrument(sample_time, note, base_frequency);
        }

        global_result += result;
    }

    /* do we need this tanh ? */

    global_result = tanh(global_result);

    dst[id] = global_result;

    /* return */
}
