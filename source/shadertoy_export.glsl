
#define TIME_SPLITTING 1.0
#define NOTES_PER_SPLITTING 16


struct Xnote
{
    int tool;
    float start;
    float end;
    float frequency;
    float volume;
};


<MAIN_ARRAY>


float random(float time) {
    return fract(sin(time * 78.233) * 43758.5453123);
}


<TOOLS_FUNCTION>


vec2 mainSound(int samp, float time)
{
    float s = time;
    float rnd = random(time) * 2.0 - 1.0;
    float res = 0.0;

    // iterate from notes
    int beat = int(floor(s / float(TIME_SPLITTING)));
    
    for (int n = 0; n < NOTES_PER_SPLITTING; ++n)
    {
            if (array[beat * NOTES_PER_SPLITTING + n].tool != -1 && array[beat * NOTES_PER_SPLITTING + n].start <= s && s <= array[beat * NOTES_PER_SPLITTING + n].end)
        { 
            switch(array[beat * NOTES_PER_SPLITTING + n].tool)
            {
                <TOOLS_SWITCH>
            default: 
                break;   
            }
        }
    }
    
    return vec2(tanh(res));
}
