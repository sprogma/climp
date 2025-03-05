#define ENCODE(t,s,e,f,v) Cnote(uint(t) + 16u * (uint(s*LENGTH_ACCURACY + 0.5) + 16000u * uint(e*LENGTH_ACCURACY + 0.5)), uint(v * 60.0 + 0.5) + 60u * uint(f * 3000.0 + 0.5))
#define DECODE(c) Xnote(int((c).tse % 16u), float((c).tse / 16u % 16000u) / LENGTH_ACCURACY, float((c).tse / 16u / 16000u) / LENGTH_ACCURACY, float((c).fv / 60u) / 3000.0, float((c).fv % 60u) / 60.0)
struct Cnote{uint tse, fv;};
struct Xnote{int tool; float start, end, frequency, volume;};
#define C(a,b) Cnote(a, b),


float random(float time) {
    return fract(sin(time * 78.233) * 43758.5453123);
}

#TIME_STEP
#LENGTH_ACCURACY


#MUSIC_DECLARATION


#TOOLS_DECLARATION


float get_tone(float time)
{
    float res = 0.0;
    time -= 1.5;
    if (time < 0.0){return 0.0;}
    int segment = int(time / TIME_STEP);
    int start;
    if (segment > min_arr.length())
    {
        start = arr.length();
    }
    else
    {
        start = min_arr[segment];
    }
    
    for (int i = start; i < arr.length(); ++i)
    {
        Xnote x = DECODE(arr[i]);
        if (time < x.start)
        {
            break;
        }
        if (x.start <= time && time <= x.end)
        {
            x.start *= 44100.0;
            x.end *= 44100.0;
            switch (x.tool)
            {
#CHECK_DECLARATION
            default:
                res += sin(6.2831*x.frequency*time) * x.volume;
            }   
        }
    }
    return res;
}
vec2 mainSound( int samp, float time )
{
    float res = 0.0;
    res += get_tone(time);
    return tanh(vec2(res, res));
}
