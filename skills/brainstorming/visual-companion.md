# Visual Companion Guide

The visual companion is a browser-based tool for displaying mockups, diagrams, and visual options during brainstorming.

## When to use
Use the browser for visual content. Use the terminal for text/tabular content.

## How it works
A local server watches a directory for HTML files and serves the newest one.

## Starting a session
Launch via `scripts/start-server.sh` with `--project-dir` and `--open` flags.

## Content fragments
Write bare HTML without <html/>/doctype; the server wraps it in a frame template.
