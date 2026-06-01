# typecmds.h

- **Source path:** `source/src/include/commands/typecmds.h`
- **Lines:** 63
- **Last verified commit:** `ef6a95c7c64`

Defines `DEFAULT_TYPDELIM = ','`. Prototypes: `DefineType`, `RemoveTypeById`, `DefineDomain`, `DefineEnum`, `DefineRange`, `AlterEnum`, `DefineCompositeType`, plus ALTER DOMAIN family (`AlterDomainDefault`, `AlterDomainNotNull`, `AlterDomainAddConstraint`, `AlterDomainValidateConstraint`, `AlterDomainDropConstraint`), domain-name helpers (`GetDomainConstraints`, `domainAddCheckConstraint`, `domainAddNotNullConstraint`), and the cascade helpers (`RenameType`, `AlterTypeOwner`, `AlterTypeOwner_oid`, `AlterTypeOwnerInternal`).
