#!/bin/bash
sed -n '/^    \$ / s/^    \$ // p' demo/demo.md | doitlive play -p osx_color -q -
