use std::env;
use std::path::PathBuf;
use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=app.rc");
    println!("cargo:rerun-if-changed=assets/app_icon.ico");

    let rc = find_resource_compiler().expect("Windows SDK resource compiler rc.exe was not found");
    let out_dir = PathBuf::from(env::var("OUT_DIR").expect("OUT_DIR is not set"));
    let res_file = out_dir.join("app_icon.res");

    let status = Command::new(rc)
        .args(["/nologo", "/fo"])
        .arg(&res_file)
        .arg("app.rc")
        .status()
        .expect("failed to run rc.exe");

    if !status.success() {
        panic!("rc.exe failed to compile app.rc");
    }

    println!("cargo:rustc-link-arg={}", res_file.display());
}

fn find_resource_compiler() -> Option<PathBuf> {
    if let Ok(path) = which("rc.exe") {
        return Some(path);
    }

    let kits = PathBuf::from(r"C:\Program Files (x86)\Windows Kits\10\bin");
    let mut candidates = Vec::new();
    if let Ok(versions) = std::fs::read_dir(kits) {
        for version in versions.flatten() {
            let path = version.path().join("x64").join("rc.exe");
            if path.exists() {
                candidates.push(path);
            }
        }
    }
    candidates.sort();
    candidates.pop()
}

fn which(name: &str) -> Result<PathBuf, ()> {
    let Some(path_var) = env::var_os("PATH") else {
        return Err(());
    };
    for path in env::split_paths(&path_var) {
        let candidate = path.join(name);
        if candidate.exists() {
            return Ok(candidate);
        }
    }
    Err(())
}
