{
  description = "Nix python flake";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      virtualisation.docker.enable = true;

      pythonEnv = pkgs.python3.withPackages (ps: with ps; [
        pip
        typer
        email-validator
        psycopg
        flask
      ]);
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        name = "python";
        buildInputs = [
          pythonEnv
          pkgs.docker
        ];
      };
    };
}