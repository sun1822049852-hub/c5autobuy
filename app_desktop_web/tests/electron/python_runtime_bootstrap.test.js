import path from "node:path";

import { describe, expect, it, vi } from "vitest";

import {
  downloadRuntimeArchive,
  ensureManagedPythonRuntime,
  patchEmbeddableRuntime,
} from "../../python_runtime_bootstrap.js";


function createRuntimeConfig() {
  return {
    archiveFileName: "python-3.11.9-embeddable-amd64.zip",
    arch: "x64",
    downloadsDirName: "python-runtime-downloads",
    manifestFileName: "runtime-manifest.json",
    pthFileName: "python311._pth",
    pythonDepsDirName: "python_deps",
    runtimeRootDirName: "python-runtime",
    sha256: "expected-sha256",
    sitePackagesRelativePath: path.join("Lib", "site-packages"),
    stagingDirName: ".python-runtime-staging",
    url: "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embeddable-amd64.zip",
    version: "3.11.9",
  };
}


describe("packaged python runtime bootstrap", () => {
  it("reuses an existing managed runtime when manifest and python executable are both present", async () => {
    const downloadRuntimeArchiveImpl = vi.fn();
    const expectedPythonExecutable = path.join(
      "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private",
      "python-runtime",
      "3.11.9",
      "python.exe",
    );
    const expectedManifestPath = path.join(
      "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private",
      "python-runtime",
      "3.11.9",
      "runtime-manifest.json",
    );
    const expectedPthPath = path.join(
      "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private",
      "python-runtime",
      "3.11.9",
      "python311._pth",
    );
    const expectedSitePackagesPath = path.join(
      "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private",
      "python-runtime",
      "3.11.9",
      "Lib",
      "site-packages",
    );

    const result = await ensureManagedPythonRuntime({
      appPrivateDir: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private",
      packagedPythonDepsPath: "C:/Program Files/C5/resources/python_deps",
      projectRoot: "C:/Program Files/C5/resources",
      runtimeConfig: createRuntimeConfig(),
      existsSync(targetPath) {
        return [
          expectedPythonExecutable,
          expectedManifestPath,
          expectedPthPath,
          expectedSitePackagesPath,
        ].includes(targetPath);
      },
      readFileSync(targetPath) {
        if (targetPath === expectedManifestPath) {
          return JSON.stringify({
            sha256: "expected-sha256",
            version: "3.11.9",
          });
        }
        throw new Error(`unexpected read: ${targetPath}`);
      },
      downloadRuntimeArchiveImpl,
    });

    expect(downloadRuntimeArchiveImpl).not.toHaveBeenCalled();
    expect(result.pythonExecutable).toBe(expectedPythonExecutable);
  });

  it("downloads, verifies, extracts and installs packaged python deps when runtime is missing", async () => {
    const downloadRuntimeArchiveImpl = vi.fn().mockResolvedValue({
      archivePath: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/python-runtime-downloads/python-3.11.9.zip",
    });
    const verifyRuntimeArchiveImpl = vi.fn().mockResolvedValue(undefined);
    const extractRuntimeArchiveImpl = vi.fn().mockResolvedValue({
      extractedRuntimeRoot: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/.python-runtime-staging/runtime",
      pythonExecutable: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/.python-runtime-staging/runtime/python.exe",
    });
    const installPackagedPythonDepsImpl = vi.fn().mockResolvedValue(undefined);
    const finalizeManagedRuntimeImpl = vi.fn().mockResolvedValue({
      pythonExecutable: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/python-runtime/3.11.9/python.exe",
    });

    const result = await ensureManagedPythonRuntime({
      appPrivateDir: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private",
      packagedPythonDepsPath: "C:/Program Files/C5/resources/python_deps",
      projectRoot: "C:/Program Files/C5/resources",
      runtimeConfig: createRuntimeConfig(),
      existsSync: vi.fn(() => false),
      downloadRuntimeArchiveImpl,
      verifyRuntimeArchiveImpl,
      extractRuntimeArchiveImpl,
      installPackagedPythonDepsImpl,
      finalizeManagedRuntimeImpl,
    });

    expect(downloadRuntimeArchiveImpl).toHaveBeenCalledOnce();
    expect(verifyRuntimeArchiveImpl).toHaveBeenCalledWith(expect.objectContaining({
      archivePath: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/python-runtime-downloads/python-3.11.9.zip",
      runtimeConfig: expect.objectContaining({ sha256: "expected-sha256" }),
    }));
    expect(extractRuntimeArchiveImpl).toHaveBeenCalledOnce();
    expect(installPackagedPythonDepsImpl).toHaveBeenCalledWith(expect.objectContaining({
      packagedPythonDepsPath: "C:/Program Files/C5/resources/python_deps",
      extractedRuntimeRoot: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/.python-runtime-staging/runtime",
    }));
    expect(finalizeManagedRuntimeImpl).toHaveBeenCalledOnce();
    expect(result.pythonExecutable).toBe("C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/python-runtime/3.11.9/python.exe");
  });

  it("redownloads when manifest exists but packaged runtime support files are missing", async () => {
    const downloadRuntimeArchiveImpl = vi.fn().mockResolvedValue({
      archivePath: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/python-runtime-downloads/python-3.11.9.zip",
    });
    const verifyRuntimeArchiveImpl = vi.fn().mockResolvedValue(undefined);
    const extractRuntimeArchiveImpl = vi.fn().mockResolvedValue({
      extractedRuntimeRoot: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/.python-runtime-staging/runtime",
      pythonExecutable: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/.python-runtime-staging/runtime/python.exe",
    });
    const installPackagedPythonDepsImpl = vi.fn().mockResolvedValue(undefined);
    const finalizeManagedRuntimeImpl = vi.fn().mockResolvedValue({
      pythonExecutable: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/python-runtime/3.11.9/python.exe",
    });
    const runtimeConfig = createRuntimeConfig();
    const runtimeRoot = path.join(
      "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private",
      "python-runtime",
      "3.11.9",
    );
    const pythonExecutable = path.join(runtimeRoot, "python.exe");
    const manifestPath = path.join(runtimeRoot, "runtime-manifest.json");

    const result = await ensureManagedPythonRuntime({
      appPrivateDir: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private",
      packagedPythonDepsPath: "C:/Program Files/C5/resources/python_deps",
      projectRoot: "C:/Program Files/C5/resources",
      runtimeConfig,
      existsSync(targetPath) {
        return targetPath === pythonExecutable || targetPath === manifestPath;
      },
      readFileSync(targetPath) {
        if (targetPath === manifestPath) {
          return JSON.stringify({
            sha256: "expected-sha256",
            version: "3.11.9",
          });
        }
        throw new Error(`unexpected read: ${targetPath}`);
      },
      downloadRuntimeArchiveImpl,
      verifyRuntimeArchiveImpl,
      extractRuntimeArchiveImpl,
      installPackagedPythonDepsImpl,
      finalizeManagedRuntimeImpl,
    });

    expect(downloadRuntimeArchiveImpl).toHaveBeenCalledOnce();
    expect(result.pythonExecutable).toBe("C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/python-runtime/3.11.9/python.exe");
  });

  it("cleans the downloaded archive when checksum verification fails", async () => {
    const removePathImpl = vi.fn();

    await expect(ensureManagedPythonRuntime({
      appPrivateDir: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private",
      packagedPythonDepsPath: "C:/Program Files/C5/resources/python_deps",
      projectRoot: "C:/Program Files/C5/resources",
      runtimeConfig: createRuntimeConfig(),
      existsSync: vi.fn(() => false),
      downloadRuntimeArchiveImpl: vi.fn().mockResolvedValue({
        archivePath: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/python-runtime-downloads/python-3.11.9.zip",
      }),
      verifyRuntimeArchiveImpl: vi.fn().mockRejectedValue(new Error("checksum mismatch")),
      removePathImpl,
    })).rejects.toThrow("checksum mismatch");

    expect(removePathImpl).toHaveBeenCalledWith("C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/python-runtime-downloads/python-3.11.9.zip");
  });

  it("cleans the staging runtime when extraction succeeds but dependency install fails", async () => {
    const removePathImpl = vi.fn();

    await expect(ensureManagedPythonRuntime({
      appPrivateDir: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private",
      packagedPythonDepsPath: "C:/Program Files/C5/resources/python_deps",
      projectRoot: "C:/Program Files/C5/resources",
      runtimeConfig: createRuntimeConfig(),
      existsSync: vi.fn(() => false),
      downloadRuntimeArchiveImpl: vi.fn().mockResolvedValue({
        archivePath: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/python-runtime-downloads/python-3.11.9.zip",
      }),
      verifyRuntimeArchiveImpl: vi.fn().mockResolvedValue(undefined),
      extractRuntimeArchiveImpl: vi.fn().mockResolvedValue({
        extractedRuntimeRoot: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/.python-runtime-staging/runtime",
        pythonExecutable: path.join("C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/.python-runtime-staging/runtime", "python.exe"),
      }),
      installPackagedPythonDepsImpl: vi.fn().mockRejectedValue(new Error("deps install failed")),
      removePathImpl,
    })).rejects.toThrow("deps install failed");

    expect(removePathImpl).toHaveBeenCalledWith("C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/.python-runtime-staging/runtime");
  });

  it("fails closed when the python runtime download hangs past the timeout", async () => {
    const clearTimeoutImpl = vi.fn();
    const fetchImpl = vi.fn((_url, { signal }) => new Promise((_resolve, reject) => {
      if (signal.aborted) {
        reject(signal.reason);
        return;
      }
      signal.addEventListener("abort", () => {
        reject(signal.reason);
      }, { once: true });
    }));

    await expect(downloadRuntimeArchive({
      archivePath: "C:/Users/tester/AppData/Roaming/C5AccountCenter/app-private/python-runtime-downloads/python-3.11.9.zip",
      clearTimeoutImpl,
      fetchImpl,
      mkdirSync: vi.fn(),
      runtimeConfig: createRuntimeConfig(),
      setTimeoutImpl(callback) {
        callback();
        return 1;
      },
      timeoutMs: 1234,
    })).rejects.toThrow("timed out after 1234ms");

    expect(fetchImpl).toHaveBeenCalledWith(
      "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embeddable-amd64.zip",
      expect.objectContaining({
        signal: expect.any(Object),
      }),
    );
    expect(clearTimeoutImpl).toHaveBeenCalledWith(1);
  });

  it("patches the embeddable pth to include cwd and packaged site-packages without enabling user site", () => {
    const writtenFiles = new Map();
    const runtimeConfig = createRuntimeConfig();

    patchEmbeddableRuntime({
      copyFileSync: vi.fn(),
      extractedRuntimeRoot: "C:/runtime",
      lstatSync(targetPath) {
        return {
          isDirectory: () => targetPath.endsWith(path.join("Lib", "site-packages")),
        };
      },
      mkdirSync: vi.fn(),
      packagedPythonDepsPath: "C:/resources/python_deps",
      projectRoot: "C:/Program Files/C5/resources",
      readFileSync(targetPath) {
        if (targetPath === path.join("C:/runtime", runtimeConfig.pthFileName)) {
          return [
            "python311.zip",
            ".",
            "# Uncomment to run site.main() automatically",
            "#import site",
          ].join("\n");
        }
        throw new Error(`unexpected read: ${targetPath}`);
      },
      readdirSync: vi.fn(() => []),
      runtimeConfig,
      writeFileSync(targetPath, content) {
        writtenFiles.set(targetPath, content);
      },
    });

    const pthContent = writtenFiles.get(path.join("C:/runtime", runtimeConfig.pthFileName));
    expect(pthContent).toContain(".");
    expect(pthContent).toContain("C:/Program Files/C5/resources");
    expect(pthContent).toContain("Lib/site-packages");
    expect(pthContent).not.toContain("import site");
  });
});
