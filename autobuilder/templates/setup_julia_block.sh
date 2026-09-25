apt-get install -y curl
if ! command -v julia >/dev/null 2>&1; then
    JULIA_VERSION="1.10.4"
    curl -fsSL "https://julialang-s3.julialang.org/bin/linux/x64/${JULIA_VERSION%.*}/julia-${JULIA_VERSION}-linux-x86_64.tar.gz" -o /tmp/julia.tar.gz
    tar -xzf /tmp/julia.tar.gz -C /opt
    ln -sf "/opt/julia-${JULIA_VERSION}/bin/julia" /usr/local/bin/julia
    rm /tmp/julia.tar.gz
fi
julia -e 'using Pkg; Pkg.add(["JSON"{JULIA_PLOTS}]); Pkg.precompile()'
