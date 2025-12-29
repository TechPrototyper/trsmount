class Trsmount < Formula
  include Language::Python::Virtualenv

  desc "FUSE filesystem for TRS-80 disk images"
  homepage "https://github.com/timw/trsdsk"
  url "https://github.com/timw/trsdsk/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "REPLACE_WITH_SHA256"
  license "MIT"

  depends_on "python@3.13"
  # Note: Requires a FUSE implementation like macFUSE or FUSE-T
  # brew install --cask macfuse
  # or
  # brew install --cask fuse-t

  resource "fusepy" do
    url "https://files.pythonhosted.org/packages/source/f/fusepy/fusepy-3.0.1.tar.gz"
    sha256 "fca936bdaa3a5e7f577df0511b4bff612c99dc7a451993d3d0ff32d133eb4a61"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/trsmount", "--help"
  end
end
