load("./a.star", "f")

# Should result in an error because the default argument of f is expected to be
# frozen at this point, but currently our unsandboxed execution backend is not
# implementing proper freezing, so this is going to succeed in our case...
val = f(3)
