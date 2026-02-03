# From the "Functions" section of the Starlark spec

def f(x, list=[]):
  list.append(x)
  return list

f(1)                    # [1]
f(2)                    # [1, 2], not [2]!
