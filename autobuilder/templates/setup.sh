#!/usr/bin/env bash
set -ex

apt-get update
apt-get install -y python3.10 python3-pip python3-dev curl

python3.10 -m pip install -U pip
python3.10 -m pip install --break-system-packages -r /autograder/source/requirements.txt

# Julia (only needed if the rubric/assignment may receive .jl submissions --
# installed unconditionally since detection happens per-submission at
# grading time, not at setup time).
if ! command -v julia >/dev/null 2>&1; then
    JULIA_VERSION="1.10.4"
    curl -fsSL "https://julialang-s3.julialang.org/bin/linux/x64/${JULIA_VERSION%.*}/julia-${JULIA_VERSION}-linux-x86_64.tar.gz" -o /tmp/julia.tar.gz
    tar -xzf /tmp/julia.tar.gz -C /opt
    ln -sf "/opt/julia-${JULIA_VERSION}/bin/julia" /usr/local/bin/julia
    rm /tmp/julia.tar.gz
fi
julia -e 'using Pkg; Pkg.add("JSON"); Pkg.precompile()'

echo "Setup complete"
