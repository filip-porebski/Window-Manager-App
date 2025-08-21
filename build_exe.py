import os
import subprocess
import sys
import shutil
from pathlib import Path
from typing import List

class BuildConfig:
    """Configuration settings for the build process."""
    APP_NAME = "windowmanagerapp"
    VERSION = "1.0.2"
    AUTHOR = "Filip Porebski"
    DESCRIPTION = "Window Manager Application"
    
    # Build settings
    ENTRY_POINT = "main.py"
    ICON_FILE = "app_icon.ico"
    REQUIRED_FILES = ["settings.json"]
    OUTPUT_DIR = "dist"
    BUILD_DIR = "build"

class ExecutableBuilder:
    """Handles the build process for creating the executable."""
    
    def __init__(self):
        self.config = BuildConfig()
        self._validate_requirements()

    def _validate_requirements(self) -> None:
        """Validate all required files and dependencies exist."""
        missing_files = []
        
        # Check if PyInstaller is available
        try:
            subprocess.run(["pyinstaller", "--version"], 
                         capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Error: PyInstaller is not installed or not in PATH.")
            print("Please install it with: pip install pyinstaller")
            sys.exit(1)
        
        # Check entry point
        if not Path(self.config.ENTRY_POINT).exists():
            missing_files.append(self.config.ENTRY_POINT)
            
        # Check icon
        if not Path(self.config.ICON_FILE).exists():
            missing_files.append(self.config.ICON_FILE)
            
        # Check required files
        for file in self.config.REQUIRED_FILES:
            if not Path(file).exists():
                missing_files.append(file)
        
        if missing_files:
            print("Error: Missing required files:")
            for file in missing_files:
                print(f"  - {file}")
            sys.exit(1)

    def _clean_build_directories(self) -> None:
        """Clean up previous build artifacts."""
        for directory in [self.config.OUTPUT_DIR, self.config.BUILD_DIR]:
            if Path(directory).exists():
                try:
                    shutil.rmtree(directory)
                    print(f"Cleaned {directory} directory")
                except Exception as e:
                    print(f"Warning: Could not clean {directory}: {e}")

    def _get_pyinstaller_command(self) -> List[str]:
        """Generate PyInstaller command with all necessary options."""
        return [
            "pyinstaller",
            "--onefile",
            "--noconsole",
            "--clean",
            f"--name={self.config.APP_NAME}",
            f"--icon={self.config.ICON_FILE}",
            "--version-file=version.txt",
            *[f"--add-data={file};." for file in self.config.REQUIRED_FILES],
            self.config.ENTRY_POINT
        ]

    def _create_version_info(self) -> None:
        """Create version info file for Windows executable."""
        version_info = f"""
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({self.config.VERSION.replace('.', ', ')}, 0),
    prodvers=({self.config.VERSION.replace('.', ', ')}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'{self.config.AUTHOR}'),
         StringStruct(u'FileDescription', u'{self.config.DESCRIPTION}'),
         StringStruct(u'FileVersion', u'{self.config.VERSION}'),
         StringStruct(u'InternalName', u'{self.config.APP_NAME}'),
         StringStruct(u'OriginalFilename', u'{self.config.APP_NAME}.exe'),
         StringStruct(u'ProductName', u'{self.config.APP_NAME}'),
         StringStruct(u'ProductVersion', u'{self.config.VERSION}')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
        with open("version.txt", "w") as f:
            f.write(version_info)

    def build(self) -> None:
        """Execute the build process."""
        try:
            print(f"Starting build process for {self.config.APP_NAME} v{self.config.VERSION}")
            
            # Clean previous builds
            self._clean_build_directories()
            
            # Create version info
            self._create_version_info()
            
            # Build executable
            print("Building executable...")
            result = subprocess.run(
                self._get_pyinstaller_command(),
                check=True,
                capture_output=True,
                text=True
            )
            
            # Clean up version file
            if Path("version.txt").exists():
                os.remove("version.txt")
            
            print("\nBuild completed successfully!")
            print(f"Executable location: {self.config.OUTPUT_DIR}/{self.config.APP_NAME}.exe")
            
        except subprocess.CalledProcessError as e:
            print("Error during build process:")
            print(f"Return code: {e.returncode}")
            if e.stdout:
                print(f"Standard output:\n{e.stdout}")
            if e.stderr:
                print(f"Standard error:\n{e.stderr}")
            print("\nTry running the command manually to see more details:")
            print(" ".join(self._get_pyinstaller_command()))
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error during build: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            sys.exit(1)

def main():
    """Main entry point for the build script."""
    builder = ExecutableBuilder()
    builder.build()

if __name__ == "__main__":
    main()