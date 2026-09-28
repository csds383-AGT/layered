{
  description = "Nix python flake";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};

      pythonEnv = pkgs.python3.withPackages (ps: with ps; [
        pip
        typer
        email-validator
      ]);
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        name = "python";
        buildInputs = [
          pythonEnv
        ];
      };
    };
}