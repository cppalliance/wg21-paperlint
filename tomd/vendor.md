# Vendored `tomd`

This directory is a **copy** of the upstream [cppalliance/tomd](https://github.com/cppalliance/tomd) repository, not a live submodule. The tree in this repo should match the following upstream revision unless you intentionally resync.

| Field | Value |
| --- | --- |
| **Upstream commit** | `556cb4a84f1d58ffd6fede1ecf081a2760d7748c` |
| **Commit URL** | https://github.com/cppalliance/tomd/commit/556cb4a84f1d58ffd6fede1ecf081a2760d7748c |

## Resyncing from upstream

1. Clone or fetch [https://github.com/cppalliance/tomd](https://github.com/cppalliance/tomd).
2. Check out the desired commit (or stay on the SHA above for a no-op refresh).
3. Replace the contents of this `tomd/` directory with that checkout (excluding this `vendor.md` if you regenerate it, or edit the table after copying).
4. Run tests for both `tomd` and `paperlint`, then commit the updated tree and **update this file** with the new SHA and URL.

Paperlint installs this copy via `pip install -e ./tomd` or the path dependency in the parent `pyproject.toml`.
