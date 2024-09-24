#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "CL\cl.h"


#include "mx_phys.h"



#define FULL_STEPS 1000000
#define DUMP_STEP 300


int main(int argc, char ** argv)
{
    srand(time(NULL));
    struct system *s = malloc(sizeof(*s));
    FILE *dump_file = fopen("dump.log", "wb");



    mx_phys_init(0);

    mx_system_init(s, "kernel.cl", 100, 100, 100, dump_file);

    // dump system.

    mx_system_dump(s);

    // allocate buffer for points

    char bf[] = "####################################################################################################";

    printf("Wait...\n");
    for (int i = 0; i < FULL_STEPS; ++i)
    {
        mx_system_move(s);
        if (i % DUMP_STEP == 0)
        {
            mx_system_dump(s);
            int c = ((double)i / FULL_STEPS) * 100;
            printf("\r|%-100.*s| %4.1f%%", c, bf, ((double)i / FULL_STEPS) * 100);
        }
    }
    printf("\r|%100.*s| 100.0%%", 100, bf);
    printf("\nEnded.\n");

    system("py visual.py");

    return 0;
}
/*


    // encode text
    while (encoded_position < text_len)
    {
        input_shift = encoded_position;
        clSetKernelArg(kernel, 2, sizeof(input_shift), (void*) &input_shift);

        err = SL_run(0, 0, kernel, shape);
        SL_finish_queues_on_platform(0);

        // 7. Look at the results via synchronous buffer map.
        cl_uint4 *ptr;
        ptr = (cl_uint4 *)clEnqueueMapBuffer( SL_queues[0][0],
                                            result_buffer,
                                            CL_TRUE,
                                            CL_MAP_READ,
                                            0,
                                            NWITEMS * sizeof(cl_uint4),
                                            0, NULL, NULL, NULL );
        SL_finish_queues_on_platform(0);
        int best_value = -1000;
        unsigned int best_seed, best_step, best_length, best_error;
        for (int i = 0; i < NWITEMS; ++i) // for i in item:
        {
            // compare them by first value - total length and second - total error
            int length = ptr[i].s0, error = ptr[i].s1;
            unsigned int seed = ptr[i].s2, step = ptr[i].s3;
            //printf("Got [%12u|%12u] => [length=%d error=%d]\n", seed, step, length, error);
            int value = length * 3 - error;
            if (best_value < value)
            {
                value = best_value;
                best_seed = seed;
                best_step = step;
                best_length = length;
                best_error = error;
            }
        }

        printf("BEST: seed=%12u step=%12u   =>    length=%-5u error=%-5u\n", best_seed, best_step, best_length, best_error);
        code[code_len++] = (struct encoding){
            best_seed,
            best_step,
            best_length
        };
        errn += best_error;
        encoded_position += best_length;
    }

    // print code, and message

    for (int i = 0; i < code_len; ++i)
    {
        printf("[%x|%x:%d]", code[i].start, code[i].step, code[i].length);
    }
    putchar('\n');
    int sa = code_len * 2 * sizeof(int) + code_len, sb = text_len;
    printf("Total length: %d bytes from %d (%f%% compression) error - %f%%\n", sa, sb, 100.0f * (float)sa / (float)sb, 100.0f * (float)errn / (float)text_len);

    // decode message.
    char s[1024 * 4] = {}, sid = 0;
    for (int i = 0; i < code_len; ++i)
    {
        unsigned seed = code[i].start;
        for (int c = 0; c < code[i].length; ++c)
        {
            s[sid++] = alphabet[seed & 0x3F];
            seed += code[i].step;
        }
    }

    printf("--------------------------------------\n%.*s\n--------------------------------------\n", sid, s);

    free(code);

    return 0;
}
*/
