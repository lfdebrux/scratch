#!/bin/sh

echo -n 'What is your name? '

read NAME

if [ ! -z "$NAME" ]
then
  echo Hello, $NAME!
else
  echo Hello, world!
fi
