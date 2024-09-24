
#define delta_time 0.001
#define delta_time_2 (delta_time * delta_time)

struct point
{
    float3 pos;
    float3 ppos;
    float3 force;
    int type;
};


float type_mass[3] = {1.0, 1.0, 0.0005446623093};
float type_charge[3] = {1.0, 0.0, -1.0};



kernel void phys_a( __global struct point *points, int points_len )
{
    /* nothing. [place to optimisation grid creation] */
    return;
}


kernel void phys_b( __global struct point *points, int points_len )
{
    /* calculate forces */
    int id = get_global_id(0);

    float3 force = 0;

    for (int i = 0; i < points_len; ++i)
    {
        if (i != id)
        {
            float3 to_it = points[i].pos - points[id].pos;
            if (length(to_it) > 0.000001)
            {
                float3 dir = normalize(to_it);
                float d = length(to_it);

                // apply gravitation:
                force += dir * 0.01 * type_mass[points[id].type] * type_mass[points[i].type] / (d * d);

                // apply charge:
                force -= dir * 15.0 * type_charge[points[id].type] * type_charge[points[i].type] / (d * d);

                // apply strong z
                if (points[id].type ^ points[i].type == 2)
                {
                    force += dir * 150.0 * type_mass[points[id].type] * type_mass[points[i].type] / pow(d, 1.8);
                    force -= dir * 200.0 * type_mass[points[id].type] * type_mass[points[i].type] / pow(d, 2.14);
                }
            }
            else
            {
                int rid = (id * 125913) % 257 * 179;
                float3 f = (float3)((float)(rid % 105 - 52), (float)(rid % 107 - 53), (float)(rid % 111 - 55));
                force += f * 0.01;
            }
        }
    }

    points[id].force = force;
}


kernel void phys_c( __global struct point *points, int points_len )
{
    /* move points */
    int id = get_global_id(0);

    float3 ppos = points[id].pos;
    float this_mass = type_mass[points[id].type];
    points[id].pos = 2.0 * points[id].pos - points[id].ppos + points[id].force / this_mass * delta_time_2;
    points[id].ppos = ppos;
}
