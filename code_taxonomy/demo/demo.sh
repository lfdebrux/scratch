#!/bin/bash
sed -n '/^    \$ / s/^    \$ // p' demo.md | doitlive play -q -
