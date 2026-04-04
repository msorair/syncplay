{
  lib,
  stdenv,
  python3Packages,
  qt6,
  enableGUI ? true,
}: let
  inherit (lib) cleanSource;
in
  python3Packages.buildPythonApplication (finalAttrs: {
    pname = "syncplay";
    version = "1.7.5";

    pyproject = false;

    src = cleanSource ./.;

    buildInputs = lib.optionals enableGUI [
      (
        if stdenv.hostPlatform.isLinux
        then qt6.qtwayland
        else qt6.qtbase
      )
    ];
    dependencies = with python3Packages;
      [
        certifi
        pem
        twisted
      ]
      ++ twisted.optional-dependencies.tls
      ++ lib.optional enableGUI pyside6
      ++ lib.optional (stdenv.hostPlatform.isDarwin && enableGUI) appnope;
    nativeBuildInputs = lib.optionals enableGUI [qt6.wrapQtAppsHook];

    makeFlags = [
      "DESTDIR="
      "PREFIX=$(out)"
    ];

    postFixup = lib.optionalString enableGUI ''
      wrapQtApp $out/bin/syncplay
    '';

    meta = {
      homepage = "https://syncplay.pl/";
      description = "Free software that synchronises media players";
      license = lib.licenses.asl20;
      platforms = lib.platforms.linux ++ lib.platforms.darwin;
      maintainers = with lib.maintainers; [assistant];
    };
  })
