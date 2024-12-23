# climp
Command Line Interface Music Player written with python and c + opencl

# music player
<table>
    <tr>
        <td><img src="./examples/player1.png" alt="./examples/player1.png"></td>
        <td><img src="./examples/player2.png" alt="./examples/player2.png"></td>
        <td><img src="./examples/player3.png" alt="./examples/player3.png"></td>
    </tr>
</table>


* Tested only on Windows yet.
* Console music player, supports some formats (mp3, wav, ogg, midi, may be others).
* Real time spectrogram of playing music.
* Albums (not implemented many albums, and their saving/loading).
* Music processing: speeding, pitching, other filters and features (open for implementations).
* Explorer screen to find music.
* Simple console to music loading, listening and processing, supporting async tasks, cycles (for mass processing), functions, etc.
* Saving processed tracks in wav format

# music writer
<table>
    <tr>
        <td><img src="./examples/writer1.png" alt="./examples/writer1.png"></td>
        <td><img src="./examples/writer2.png" alt="./examples/writer2.png"></td>
        <td><img src="./examples/writer3.png" alt="./examples/writer3.png"></td>
    </tr>
</table>

* Support synthesizer mode (base sound coding, with low not standard music support (like micro-tonal music, etc.)), other modes maybe appear later (this one is sufficient).
* Easy writing code-like language.
* Powerful tools system. You can manage OpenCL kernel code for each tool, and make any sound, as you want.
* Bad-working (but working) auto tool creation system (from music file (wav, mp3, etc.)) 
* Uses gpu to generate sound samples (fast).

# music processing

some examples of processed music



<table>
    
<tr><td>Originals</td>
<td>

https://github.com/user-attachments/assets/c7946e4b-bf31-40be-b298-ac7aab174874

</td><td>

https://github.com/user-attachments/assets/0f515f60-85b4-410d-b825-98f3980cd2e4

</td><td>

https://github.com/user-attachments/assets/f8000325-fd84-4c22-8bd2-a0ba2c99d8a4

</tr><tr><td>Simple scaling (every second sample)</td>
<td>

https://github.com/user-attachments/assets/3f9a29e2-6b92-481b-8953-137b9245d756

</td><td>
    
https://github.com/user-attachments/assets/70ad1cc2-8969-4421-a8fc-b0409ddfb781

</td><td>
    
https://github.com/user-attachments/assets/a85b9017-15ea-40a4-b1f6-a5cc358ca663

</td></tr><tr><td>Reversing, using beat notes</td>
<td>

https://github.com/user-attachments/assets/ddee0b16-e14e-4c86-8b97-3a6e2591a4c9
    
</td><td>

https://github.com/user-attachments/assets/f81ebc72-8b07-4991-8fed-82d21fe5f237

</td><td>

https://github.com/user-attachments/assets/228cdae0-84e4-4ad8-80c9-dcc1b6311d35

</td></tr><tr><td>Tonal pitching (0.5x)</td>
<td>

https://github.com/user-attachments/assets/ba905297-1d2c-4600-a718-c97bd0d43137

</td><td>

https://github.com/user-attachments/assets/c58e5021-5fd8-4a90-9bbb-764b008dd256

</td><td>

https://github.com/user-attachments/assets/e0d360cf-9edb-4a70-992e-8abcd3374c92

</td></tr><tr><td>Speed pitching (2x)</td>
<td>

https://github.com/user-attachments/assets/0d1b115d-2329-48f2-aad5-c908594f3ffb

</td><td>

https://github.com/user-attachments/assets/f42671dc-550a-4cc5-8b24-1cf97ea75301

</td><td>

https://github.com/user-attachments/assets/92c73704-53e4-42d9-90bd-9bc5f56b3a40

</td></tr><tr><td>saw tool [jackal command] + amplitude clipping</td>
<td>

https://github.com/user-attachments/assets/baf971dc-d4ba-4789-9aa1-71230c7bc44b

</td><td>

https://github.com/user-attachments/assets/08435e53-9714-4005-80a3-289ce9181ed5

</td><td>

https://github.com/user-attachments/assets/bb81a053-cb84-4b79-b9d3-e678a4b98ee9

</td></tr>
</table>


* Almost all functions I wrote myself, so them are not best (in quality and speed) 
* Saving processed tracks in wav format
* Using console, you can process many tracks or declare functions, etc. (now, functions is not saving between sessions.)


# how to install 

* ### Windows
    1. build it with powershell:
        (run in repo directory)
        ```ps1
        .\install\windows.ps1
        ```
    2. use result in 'build' directory. (run using python "code/music_player.py", "run.bat" or "run.ps1")
* ### Linux
    test in plans (not implemented, see others part)
* ### Others
    to build it alone:
    1. Source python and c code located in 'source' directory. Run file 'music_player.py'
    2. To use c library, build it as shared object, and connect in end of 'music_player.py', using ctypes

## depend on
1. installed python (version 3.11 tested, but it maybe won't cause errors in some previous.)
2. python libs: numpy, mutagen, librosa, pygame, curses (different packages for windows and unix.). 
To install program you can use shell scripts in directory /install.
3. To use fast procedural music generation you can use c bindings with graphic card usage.
It is not tested yet. (since version 2.2.0)
you can use compiled programs, but if you need to compile it yourself,
you need: Gcc, OpenCL, [to easy install you can use Code Blocks]
