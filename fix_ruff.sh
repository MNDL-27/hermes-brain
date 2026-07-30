#!/bin/bash
pip install ruff==0.16.0
ruff check . --fix
