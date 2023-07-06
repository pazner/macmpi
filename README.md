# MacMPI

MacMPI is a tool (inspired by and based on [tmux-mpi][tmux-mpi] that can
be used to launch MPI applications, opening a new terminal window with one
tab per MPI rank, attaching each tab to the corresponding rank. MacMPI 
integrates with the [iTerm2][iterm] terminal on macOS.

This allows for debugging MPI applications by launching lldb or gdb with 
MacMPI.

## Installation

1. Install iTerm by downloading it from [the website][iterm].
2. Install dtach with `brew intall dtach`
3. Install the dependencies with `pip install -r requirements.txt`
4. Run MacMPI with `python macmpi.py <np> <command>`, where `<np>` is the
   number of ranks, and `<command>` is the command to be run (analogous to
   `mpirun -np <np> <command>`)


[tmux-mpi]: https://github.com/wrs20/tmux-mpi
[iterm]: https://iterm2.com
