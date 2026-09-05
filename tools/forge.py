#!/usr/bin/env python3
"""Shared command line for native Windows and the existing Linux/Docker tools.

The launcher provides managed Python. Importing this module does not install
dependencies or run commands. Tool processes run at the repository root; file
arguments are resolved from the caller's original working directory.
"""
import argparse
import glob
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unicodedata


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = {
    "extract": "extract.py", "figextract": "figextract.py",
    "figindex": "figindex.py", "detect": "detect_labels.py",
    "preview": "preview.py", "build": "build_deck.py",
    "validate": "validate.py", "lint": "lint_cards.py",
    "grounding": "grounding_check.py", "coverage": "coverage.py",
    "decode": "apkg_to_cards.py", "diff": "deck_diff.py",
    "anki": "anki_connect.py",
}
DOCKER_TOOLS = {"extract", "figextract", "detect", "preview", "build", "validate"}
# Only declared path arguments are rewritten. Language codes, numeric values,
# deck names and Anki field HTML are passed as individual arguments unchanged.
OPTIONS = {
    "extract": {"-o": "path", "--out": "path", "-j": "value", "--jobs": "value", "--lang": "value"},
    "figextract": {k: "value" for k in ("--zoom", "--min-area", "--max-area", "--min-side")},
    "figindex": {},
    "detect": {k: "value" for k in ("--lang", "--min-conf", "--gap-factor")},
    "preview": {"--theme": "value", "--offline": "switch"},
    "build": {}, "validate": {}, "lint": {},
    "grounding": {"--source": "path", "--min-cover": "value", "--err-cover": "value"},
    "coverage": {"--against": "path", "--threshold": "value", "--strict": "switch"},
    "decode": {"-o": "path", "--out": "path"},
    "diff": {"--strict": "switch"},
}
USAGES = {
    "prep": "prep <file/folder> [...] [--lang eng+deu] [-j N] [--zoom Z] [--min-area A] [--max-area A] [--min-side S]",
    "finish": "finish <cards.json> [...] [out.apkg] [--push] [--prune] [--sync]",
    "build": "build <cards.json> [...] [out.apkg]",
    "validate": "validate <file.apkg>", "lint": "lint <cards.json>",
}


class UsageError(ValueError):
    """Invalid command or a path outside the project."""


class CommandFailed(RuntimeError):
    def __init__(self, returncode):
        self.returncode = returncode
        super().__init__(f"Command failed with exit status {returncode}.")


def split_arguments(args, options):
    """Yield (option or None, value), supporting --name=value and -j2."""
    args = iter(args)
    positional_only = False
    for arg in args:
        if arg == "--" and not positional_only:
            positional_only = True
            continue
        if positional_only or not arg.startswith("-"):
            yield None, arg
            continue
        key, sep, value = arg.partition("=")
        if not sep and key not in options and len(arg) > 2 and arg[:2] in options:
            key, value, sep = arg[:2], arg[2:], "="
        kind = options.get(key)
        if kind is None:
            raise UsageError(f"Unknown option: {arg}")
        if kind == "switch":
            if sep:
                raise UsageError(f"{key} does not take a value.")
            yield key, None
            continue
        if not sep:
            try:
                value = next(args)
            except StopIteration:
                raise UsageError(f"{key} needs a value.") from None
            if value.startswith("--"):
                raise UsageError(f"{key} needs a value (got {value}).")
        if not value:
            raise UsageError(f"{key} needs a nonempty value.")
        yield key, value


class Forge:
    def __init__(self, root=ROOT, cwd=None, backend=None, runner=None, python=None, env=None):
        self.root = Path(root).resolve()
        self.cwd = Path(cwd or os.getcwd()).resolve()
        self.backend = backend or ("native" if os.name == "nt" else "docker")
        self.runner = runner or subprocess.run
        self.python = python or sys.executable
        self.env = dict(os.environ if env is None else env)
        self.env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

    def path(self, value):
        if not value:
            raise UsageError("Paths must not be empty.")
        path = Path(value)
        if not path.is_absolute():
            path = self.cwd / path
        path = path.resolve()
        try:
            relative = path.relative_to(self.root)
        except ValueError:
            raise UsageError(f"'{value}' is outside the project ({self.root}). Use a path inside sources/, decks/ or extracted/.") from None
        result = relative.as_posix()
        return "./" + result if result.startswith("-") else result

    def paths(self, value, expand=False):
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = self.cwd / candidate
        if expand and not candidate.exists() and glob.has_magic(str(candidate)):
            matches = sorted(glob.glob(str(candidate)))
            if not matches:
                raise UsageError(f"No inputs match: {value}")
            return [self.path(match) for match in matches]
        return [self.path(value)]

    def run(self, command, *, advisory=False):
        result = self.runner(list(map(str, command)), cwd=self.root, env=self.env)
        if result.returncode:
            if advisory:
                print(f"Note: advisory check exited with status {result.returncode}; review its output.", file=sys.stderr)
            else:
                raise CommandFailed(result.returncode)
        return result.returncode

    def tool(self, name, args, *, advisory=False):
        if self.backend == "native" and name in {"extract", "detect"}:
            self.check_ocr_languages(name, args)
        if self.backend == "docker" and name in DOCKER_TOOLS:
            command = [self.root / "tools" / (name + ".sh"), *args]
        else:
            command = [self.python, self.root / "tools" / SCRIPTS[name], *args]
        return self.run(command, advisory=advisory)

    def check_ocr_languages(self, command, args):
        tessdata = self.env.get("TESSDATA_PREFIX")
        if not tessdata:
            return  # Existing/direct tool environments still perform their own checks.
        options = dict(split_arguments(args, OPTIONS[command]))
        language_spec = options.get("--lang", "eng+deu")
        languages = [language for language in language_spec.split("+") if language]
        folder = Path(tessdata).resolve()
        missing = []
        for language in languages:
            model = (folder / (language + ".traineddata")).resolve()
            if not model.is_relative_to(folder) or not model.is_file():
                missing.append(language)
        if missing:
            raise UsageError("OCR language data is missing: " + ", ".join(missing)
                             + f". Run .\\forge.cmd setup --lang {language_spec}")

    def mapped(self, name, args):
        mapped, positional, values = [], [], {}
        for key, value in split_arguments(args, OPTIONS[name]):
            if key is None:
                expand = name in {"build", "coverage", "figindex"} and not value.lower().endswith(".apkg")
                paths = self.paths(value, expand=expand)
                mapped.extend(paths)
                positional.extend(paths)
            else:
                if OPTIONS[name][key] == "path":
                    value = self.path(value)
                mapped.append(key)
                if value is not None:
                    mapped.append(value)
                values[key] = value
        return mapped, positional, values

    def extraction_outputs(self, source, values):
        source = self.root / source
        if source.is_dir():
            sources = sorted(p for p in source.iterdir() if p.is_file()
                             and p.suffix.lower() in {".pdf", ".md", ".markdown", ".txt"}
                             and p.name.lower() not in {"context.md", "kontext.md"})
        else:
            sources = [source]
        outputs = []
        custom = values.get("--out", values.get("-o"))
        for item in sources:
            input_path = self.path(str(item))  # Check links inside input folders.
            if custom and not source.is_dir():
                output = self.root / custom
            else:
                relative = item.relative_to(self.root)
                topic = relative.parent.relative_to("sources") if relative.parts[0] == "sources" else Path()
                output = self.root / "extracted" / topic / (item.stem + ".md")
            outputs.append((input_path, self.path(str(output))))
        return outputs

    @staticmethod
    def check_output_collisions(outputs):
        by_output = {}
        for source, output in outputs:
            key = unicodedata.normalize("NFC", output).casefold()
            if key in by_output and by_output[key] != source:
                raise UsageError(f"Sources '{by_output[key]}' and '{source}' both map to '{output}'. Rename one source before extraction.")
            by_output[key] = source

    def extract(self, args, positional, values):
        outputs = self.extraction_outputs(positional[0], values)
        self.check_output_collisions(outputs)
        self.tool("extract", args)
        if self.backend == "docker":
            return  # extract.sh has already indexed its sources.
        outputs = [path for _, path in outputs if (self.root / path).is_file()]
        if outputs:
            self.tool("figindex", list(dict.fromkeys(outputs)), advisory=True)

    def prep(self, args):
        options = {k: v for k, v in OPTIONS["extract"].items() if k not in {"-o", "--out"}}
        options.update(OPTIONS["figextract"])
        inputs, extract_args, figure_args = [], [], []
        for key, value in split_arguments(args, options):
            if key is None:
                inputs.extend(self.paths(value, expand=True))
            else:
                target = figure_args if key in OPTIONS["figextract"] else extract_args
                target.extend((key, value))
        if not inputs:
            raise UsageError("Usage: forge " + USAGES["prep"])
        values = dict(split_arguments(extract_args, OPTIONS["extract"]))
        # Check every input before starting, including overlaps between folders
        # and individually named files (chapter.pdf and chapter.txt -> chapter.md).
        outputs = [pair for source in inputs for pair in self.extraction_outputs(source, values)]
        self.check_output_collisions(outputs)
        print("== 1/2 Text extract + figure index ==", flush=True)
        for source in inputs:
            self.extract([source, *extract_args], [source], values)
        print("== 2/2 Cropping figures ==", flush=True)
        for source in inputs:
            path = self.root / source
            has_pdf = any(p.is_file() and p.suffix.lower() == ".pdf" for p in path.iterdir()) if path.is_dir() else path.suffix.lower() == ".pdf"
            if has_pdf:
                self.tool("figextract", [source, *figure_args])
            else:
                print(f"(no PDFs in {source} — skipping figure crops)")
        print("Done. Read: extracted/<topic>/<name>.md (figures: <name>.figures.md / figures/)")

    def finish(self, args):
        inputs, output, flags = [], None, set()
        for key, value in split_arguments(args, {k: "switch" for k in ("--push", "--prune", "--sync")}):
            if key:
                flags.add(key)
            elif value.lower().endswith(".apkg"):
                if output is not None:
                    raise UsageError("Only one target .apkg is allowed.")
                output = self.path(value)
            elif value.lower().endswith(".json"):
                inputs.extend(self.paths(value, expand=True))
            else:
                raise UsageError(f"Unknown argument: {value} (expected *.cards.json or *.apkg)")
        for flag in ("--prune", "--sync"):
            if flag in flags and "--push" not in flags:
                raise UsageError(f"{flag} requires --push.")
        if not inputs:
            raise UsageError("Usage: forge " + USAGES["finish"])
        if output is None:
            if len(inputs) > 1:
                raise UsageError("Several inputs: name a target .apkg, e.g. decks/<topic>/<topic>-complete.apkg.")
            source = inputs[0]
            suffix = ".cards.json" if source.lower().endswith(".cards.json") else ".json"
            output = source[:-len(suffix)] + ".apkg"
        print("== Lint (structure; gate) ==", flush=True)
        for source in inputs:
            self.tool("lint", [source])
        print("== Grounding (source-text coverage; hint) ==", flush=True)
        for source in inputs:
            self.tool("grounding", [source], advisory=True)
        if len(inputs) > 1:
            print("== Coverage (duplicates/coverage across all inputs; hint) ==", flush=True)
            self.tool("coverage", inputs, advisory=True)
        print("== Build (.apkg) ==", flush=True)
        self.tool("build", [*inputs, output])
        print("== Validate (real Anki engine) ==", flush=True)
        self.tool("validate", [output])
        if "--push" in flags:
            print("== Push into Anki (AnkiConnect) ==", flush=True)
            self.tool("anki", ["push", output, *(["--prune"] if "--prune" in flags else [])])
            if "--sync" in flags:
                self.tool("anki", ["sync"])
        print(f"Done: {output}")
        for source in inputs:
            with (self.root / source).open(encoding="utf-8") as stream:
                if any(card.get("type") == "occlusion" for card in json.load(stream).get("cards", [])):
                    print("Note: occlusion cards included — render and inspect both themes: forge preview <cards.json>")
                    break

    def anki(self, args):
        if not args or args[0] in {"--help", "-h"}:
            return self.tool("anki", args)
        command, rest = args[0], args[1:]
        options = {
            "push": {k: "switch" for k in ("--no-backup", "--prune", "--dry-run")},
            "export": {}, "ping": {}, "decks": {}, "sync": {}, "mirror": {},
            "update-note": {"--field": "value", "--no-backup": "switch"},
            "restore": {"--list": "switch"},
        }
        if command not in options:
            raise UsageError(f"Unknown AnkiConnect command: {command}")
        if any(arg in {"--help", "-h"} for arg in rest):
            return self.tool("anki", args)
        mapped, position = [command], 0
        for key, value in split_arguments(rest, options[command]):
            if key is None:
                if (command == "push" and position == 0) or (command == "export" and position == 1):
                    value = self.path(value)
                position += 1
                mapped.append(value)
            else:
                mapped.append(key)
                if value is not None:
                    mapped.append(value)
        return self.tool("anki", mapped)

    def native_environment(self):
        helper = self.root / "tools" / "native_setup.py"
        if helper.is_file():
            # The helper is stdlib-only; environment() only discovers local paths.
            spec = importlib.util.spec_from_file_location("forge_native_setup", helper)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Replace rather than merge: the helper deliberately removes
            # inherited PYTHONHOME/PYTHONPATH from the complete environment.
            self.env = module.environment(self.root)
            self.env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

    def dispatch(self, command, args):
        if self.backend == "docker" and os.name == "nt":
            raise UsageError("The Docker backend uses the Linux/WSL shell tools. Use the native backend on Windows.")
        if command in USAGES and any(a in {"-h", "--help"} for a in args):
            print("Usage: forge " + USAGES[command])
            return
        if self.backend == "native":
            self.native_environment()
        if command in {"setup", "doctor"}:
            if self.backend == "native":
                self.run([self.python, self.root / "tools" / "native_setup.py", command, *args])
            elif command == "setup":
                if args:
                    raise UsageError("Docker setup takes no arguments.")
                self.run([self.root / "tools" / "setup.sh"])
            else:
                if args:
                    raise UsageError("Docker doctor takes no arguments.")
                self.run(["docker", "info"])
                print(f"Python: {self.python}\nDocker is reachable. Full setup: ./tools/setup.sh")
        elif command == "prep":
            self.prep(args)
        elif command == "finish":
            self.finish(args)
        elif command == "anki":
            self.anki(args)
        elif command == "test":
            self.run([self.python, "-m", "unittest", "discover", "-s", self.root / "tests", "-p", "test_*.py", *args])
        elif command in SCRIPTS:
            if any(a in {"--help", "-h"} for a in args):
                self.tool(command, args)
                return
            mapped, positional, values = self.mapped(command, args)
            expected = 2 if command == "diff" else 1
            if len(positional) < expected:
                raise UsageError(f"{command} needs {'two paths' if expected == 2 else 'an input path'}.")
            if command not in {"coverage", "build", "figindex"} and len(positional) != expected:
                raise UsageError(f"{command} expects {expected} input path(s).")
            if command == "extract":
                self.extract(mapped, positional, values)
            else:
                self.tool(command, mapped)
        else:
            raise UsageError(f"Unknown command: {command}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog="Run forge <command> --help for tool options. The native backend requires forge setup first.")
    parser.add_argument("--backend", choices=("native", "docker"), default=None,
                        help="default: native on Windows, docker elsewhere")
    parser.add_argument("command", choices=["setup", "doctor", "prep", "finish", *SCRIPTS, "test"], nargs="?")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        Forge(backend=args.backend).dispatch(args.command, args.args)
    except UsageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except CommandFailed as exc:
        return exc.returncode
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
