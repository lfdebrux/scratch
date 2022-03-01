#!/usr/bin/env es

echo -n 'What is your name? '

NAME = <={%read}

if {! ~ $NAME ()} {
  echo Hello, $^NAME!
} {
  echo Hello, world!
}
