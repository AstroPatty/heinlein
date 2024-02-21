#!/bin/bash
godata server start
cd tests && poetry run pytest 