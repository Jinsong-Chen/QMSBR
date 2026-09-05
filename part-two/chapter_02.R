# QMSBR Part Two, Chapter 2: analysis, verification, and render helpers.
# Canonical companion to chapter_02.qmd; source from materials/part-two.
# Sourcing defines functions only. Generation/freezing require explicit calls;
# existing canonical data and sealed model objects must never be overwritten.

# ---- generate sle samples ----

# QMSBR Part Two: frozen SLE population, appendix metadata, and one CSV.
# Original simulation 2026-09-04; lossless single-file packaging 2026-09-05.
# Source-safe: sourcing defines functions only; it never reads or writes data.
# To reproduce in a separate empty output directory, from materials/part-two:
# source("chapter_02.R"); generate_sle_samples("<separate-empty-output-dir>")
# Never regenerate the canonical observations or overwrite sealed model objects.

# The chapter renders the codebook and manifest as appendix tables.
# These declarations support book production; readers need only the CSV.
sle_codebook_lines <- function() c(
  "item,domain,indicator_definition,wording,unit,coding,missing_code,response_process",
  "P1,Planning,Planning-routine consistency,I establish a study plan before beginning a task.,process-index points,higher means more of the stated attribute,NA,hypothetical continuous index; not a single ordered-category response",
  "P2,Planning,Priority-setting clarity,I identify which study tasks deserve attention first.,process-index points,higher means more of the stated attribute,NA,hypothetical continuous index; not a single ordered-category response",
  "P3,Planning,Progress-monitoring regularity,I compare my progress with the plan I made.,process-index points,higher means more of the stated attribute,NA,hypothetical continuous index; not a single ordered-category response",
  "P4,Planning,Adaptive planning,I revise my plan when a study method is not working.,process-index points,higher means more of the stated attribute,NA,hypothetical continuous index combining planning and method adjustment",
  "S1,Strategy,Strategy-adjustment flexibility,I change my learning strategy when understanding is weak.,process-index points,higher means more of the stated attribute,NA,hypothetical continuous index; not a single ordered-category response",
  "S2,Strategy,Method-selection deliberateness,I select a learning method suited to the task.,process-index points,higher means more of the stated attribute,NA,hypothetical continuous index; not a single ordered-category response",
  "S3,Strategy,Reflective revision,I revise my explanation after checking my understanding.,process-index points,higher means more of the stated attribute,NA,hypothetical continuous index; not a single ordered-category response",
  "S4,Strategy,Socially supported strategy change,I use discussion with others to improve my learning method.,process-index points,higher means more of the stated attribute,NA,hypothetical continuous index combining learning strategy and social participation",
  "B1,Belonging,Peer acceptance,I feel accepted by other students.,process-index points,higher means more of the stated attribute,NA,hypothetical continuous experience index; shared peer context with B2",
  "B2,Belonging,Peer participation,I feel able to join other students in learning activities.,process-index points,higher means more of the stated attribute,NA,hypothetical continuous experience index; shared peer context with B1",
  "B3,Belonging,Classroom voice,I feel able to express my views in class.,process-index points,higher means more of the stated attribute,NA,hypothetical continuous experience index; not a single ordered-category response",
  "B4,Belonging,Institutional connection,I feel connected to the university as a whole.,process-index points,higher means more of the stated attribute,NA,hypothetical continuous experience index; broad content rather than one setting"
)

sle_codebook_sha256 <- function() {
  bytes <- charToRaw(paste0(paste(sle_codebook_lines(),collapse="\n"),"\n"))
  hash <- digest::digest(bytes,algo="sha256",serialize=FALSE)
  hash
}
sle_codebook <- function() {
  sle_codebook_sha256()
  read.csv(text=paste(sle_codebook_lines(),collapse="\n"),stringsAsFactors=FALSE)
}
sle_manifest <- function() {
  roles <- c("development","confirmation","revalidation")
  data.frame(sample=LETTERS[1:3],role=roles,file="sle_continuous.csv",
    n=360L,population="SLE-continuous-v1",seed=20260921:20260923,
    rng="Mersenne-Twister/Inversion/Rejection",r_version="4.5.1",
    sha256="62ae01b51c424ba820931c20fade3fa7d48148ee8bd3e4e881adbe53fc68045d",
    codebook_sha256=sle_codebook_sha256(),
    legacy_file=paste0("sle_",roles,"_continuous.csv"),
    legacy_sha256=c(
      "5ef452dad018bad724814045ffb00a2a2f714bffe14f6601096e18a80e9ccee9",
      "8b5bd130cee6f6c879449c4965c3b5d5d594597a1dae3fe678d382e5eb48a0ed",
      "7d4570f9be829da36c524225265b992d34347ef05988639402939d9287cd989b"),
    stringsAsFactors=FALSE)
}
sle_read_sample <- function(role,data_dir=".") {
  manifest <- sle_manifest()
  stopifnot(length(role)==1L,role %in% manifest$role)
  row <- manifest[manifest$role==role,,drop=FALSE]
  path <- file.path(data_dir,row$file)
  book <- sle_codebook()
  lines <- readLines(path,warn=FALSE)
  header <- paste0('"',paste(c("id",book$item),collapse='","'),'"')
  stopifnot(length(lines)==1081L,lines[1]==paste0('"sample",',header),
    all(grepl('^"[ABC]",',lines[-1])))
  # Select the evidence role before parsing indicators or computing statistics.
  records <- lines[-1][startsWith(lines[-1],paste0('"',row$sample,'",'))]
  original <- c(header,substring(records,5))
  # Explicit migration bridge: reconstruct original CRLF CSV bytes in memory.
  bytes <- charToRaw(paste0(paste(original,collapse="\r\n"),"\r\n"))
  stopifnot(length(records)==row$n,
    digest::digest(bytes,algo="sha256",serialize=FALSE)==row$legacy_sha256)
  dat <- read.csv(text=paste(original,collapse="\n"),
    stringsAsFactors=FALSE,check.names=FALSE)
  stopifnot(identical(names(dat),c("id",book$item)),!anyDuplicated(dat$id),
    all(substr(dat$id,1,1)==row$sample),!anyNA(dat[book$item]),
    all(vapply(dat[book$item],is.numeric,logical(1))),
    all(is.finite(as.matrix(dat[book$item]))))
  list(x=dat[book$item],ids=dat$id,book=book,manifest=row,
    manifest_all=manifest)
}

sle_population <- function() {
  items <- c(paste0("P", 1:4), paste0("S", 1:4), paste0("B", 1:4))
  factors <- c("Planning", "Strategy", "Belonging")
  Lambda_z <- matrix(0, 12, 3, dimnames = list(items, factors))
  Lambda_z[1:4, 1] <- c(.78, .74, .70, .55)
  Lambda_z[5:8, 2] <- c(.76, .72, .68, .55)
  Lambda_z[9:12, 3] <- c(.80, .74, .67, .50)
  Lambda_z[4, 2] <- .32
  Lambda_z[8, 3] <- .30
  Phi <- matrix(c(1,.42,.30, .42,1,.35, .30,.35,1), 3, 3,
                dimnames = list(factors, factors))
  common <- Lambda_z %*% Phi %*% t(Lambda_z)
  Theta_z <- diag(1 - diag(common))
  dimnames(Theta_z) <- list(items, items)
  # Shared peer context not fully represented by the broad factors.
  Theta_z[9, 10] <- Theta_z[10, 9] <- .12
  scale <- c(8,10,12,9, 10,8,11,9, 10,12,8,11)
  D <- diag(scale)
  nu <- setNames(c(50,52,48,51, 49,50,52,48, 51,49,50,52), items)
  Lambda <- D %*% Lambda_z
  Theta <- D %*% Theta_z %*% D
  dimnames(Lambda) <- dimnames(Lambda_z)
  dimnames(Theta) <- dimnames(Theta_z)
  stopifnot(min(eigen(Phi, symmetric=TRUE)$values) > 0,
            min(eigen(Theta, symmetric=TRUE)$values) > 0)
  list(version="SLE-continuous-v1", items=items, factors=factors,
       Lambda_z=Lambda_z, Phi=Phi, Theta_z=Theta_z, scale=scale,
       nu=nu, alpha=setNames(rep(0,3),factors), Lambda=Lambda, Theta=Theta)
}


generate_sle_samples <- function(data_dir) {
  if (!dir.exists(data_dir)) stop("Supply an existing output directory.")
  path <- file.path(data_dir,"sle_continuous.csv")
  if(file.exists(path)) stop("Existing lineage: refusing overwrite.")
  manifest <- sle_manifest()
  book <- sle_codebook()
  pop <- sle_population()
  stopifnot(identical(book$item,pop$items))
  RNGkind("Mersenne-Twister","Inversion","Rejection")
  records <- vector("list",3)
  for(k in 1:3) {
    set.seed(manifest$seed[k])
    n <- manifest$n[k]
    eta <- matrix(rnorm(n*3),n,3) %*% chol(pop$Phi)
    epsilon <- matrix(rnorm(n*12),n,12) %*% chol(pop$Theta)
    Y <- sweep(eta %*% t(pop$Lambda)+epsilon,2,pop$nu,"+")
    colnames(Y) <- pop$items
    records[[k]] <- data.frame(sample=manifest$sample[k],
      id=sprintf("%s%03d",manifest$sample[k],1:n),Y,check.names=FALSE)
  }
  record <- do.call(rbind,records)
  stopifnot(nrow(record)==1080L,!anyDuplicated(record$id))
  # Canonical CRLF serialization reproduces the original numeric tokens.
  con <- textConnection("csv","w",local=TRUE)
  write.csv(record,con,row.names=FALSE,na="NA")
  close(con)
  writeBin(charToRaw(paste0(paste(csv,collapse="\r\n"),"\r\n")),path)
  stopifnot(digest::digest(file=path,algo="sha256")==manifest$sha256[1])
  message("Frozen A/B/C reproduced in one CSV; analysis roles remain separate.")
  invisible(manifest)
}

# ---- run efa analysis ----

# QMSBR Chapter 2 analysis. Source-safe; reads Sample A only.
# Plain base R + psych 2.5.6 + GPArotation 2025.3.1; no installation.
# Exact permutation PA: seed 20260924, 1000 replicates, type-7 .95 quantiles.
# Observed/null factor target: Pearson matrix with SMC diagonal, not ML roots.

efa_read_development <- function(data_dir=".") {
  input <- sle_read_sample("development",data_dir)
  list(x=input$x,codebook=input$book,manifest=input$manifest,
    manifest_all=input$manifest_all)
}

efa_pa_roots <- function(R) {
  stopifnot(min(eigen(R,symmetric=TRUE,only.values=TRUE)$values)>1e-10)
  reduced <- R
  diag(reduced) <- 1 - 1/diag(solve(R))
  cbind(component=eigen(R,symmetric=TRUE,only.values=TRUE)$values,
        factor=eigen(reduced,symmetric=TRUE,only.values=TRUE)$values)
}

efa_permutation_pa <- function(x, reps=1000L, seed=20260924L) {
  RNGkind("Mersenne-Twister","Inversion","Rejection")
  set.seed(seed)
  observed <- efa_pa_roots(cor(x))
  null <- array(NA_real_, c(ncol(x),2,reps))
  for (b in seq_len(reps)) {
    permuted <- vapply(x, function(v) sample(v, replace=FALSE), numeric(nrow(x)))
    # Do not discard failures or smooth a matrix: stop the analysis instead.
    null[,,b] <- efa_pa_roots(cor(permuted))
  }
  reference <- apply(null,c(1,2),quantile,probs=.95,type=7)
  # Retain the leading uninterrupted run, not later isolated crossings.
  leading <- function(ok) if (all(ok)) length(ok) else which(!ok)[1]-1L
  counts <- vapply(1:2,function(j) leading(observed[,j]>reference[,j]),integer(1))
  list(observed=observed,reference=reference,null=null,reps=reps,seed=seed,
       counts=setNames(counts,c("component","factor")),failures=0L)
}

efa_extract <- function(R,n,m,fm="ml") {
  warnings <- character()
  fit <- withCallingHandlers(psych::fa(R,nfactors=m,n.obs=n,fm=fm,rotate="none",
    SMC=TRUE,min.err=1e-8,max.iter=1000,smooth=FALSE,scores="none",warnings=TRUE),
    warning=function(w) {warnings <<- c(warnings,conditionMessage(w)); invokeRestart("muffleWarning")})
  list(fit=fit,warnings=unique(warnings))
}

efa_align <- function(P,Phi,reference=NULL) {
  if (ncol(P)!=3L) return(list(P=P,Phi=Phi))
  perms <- rbind(c(1,2,3),c(1,3,2),c(2,1,3),c(2,3,1),c(3,1,2),c(3,2,1))
  if (is.null(reference)) {
    anchors <- list(1:3,5:7,9:11)
    strength <- t(vapply(anchors,function(i) colMeans(abs(P[i,,drop=FALSE])),numeric(3)))
    score <- apply(perms,1,function(p) sum(strength[cbind(1:3,p)]))
  } else {
    congruence <- t(reference) %*% P /
      sqrt(outer(colSums(reference^2),colSums(P^2)))
    score <- apply(perms,1,function(p) sum(abs(congruence[cbind(1:3,p)])))
  }
  order <- perms[which.max(score),]
  P <- P[,order,drop=FALSE]; Phi <- Phi[order,order,drop=FALSE]
  signs <- if (is.null(reference)) sign(c(sum(P[1:3,1]),sum(P[5:7,2]),sum(P[9:11,3]))) else
    sign(colSums(P*reference))
  signs[signs==0] <- 1
  P <- sweep(P,2,signs,"*"); Phi <- diag(signs)%*%Phi%*%diag(signs)
  colnames(P) <- c("Planning","Strategy","Belonging")
  dimnames(Phi) <- list(colnames(P),colnames(P))
  list(P=P,Phi=Phi)
}

efa_rotate <- function(A,method="oblimin",seed=20260925L,reference=NULL) {
  set.seed(seed)
  if (ncol(A)==1L) return(list(P=A,Phi=matrix(1),converged=TRUE))
  rot <- switch(method,
    oblimin=GPArotation::oblimin(A,gam=0,normalize=FALSE,eps=1e-7,maxit=10000,randomStarts=20),
    geomin=GPArotation::geominQ(A,delta=.01,normalize=FALSE,eps=1e-7,maxit=10000,randomStarts=20),
    varimax=GPArotation::Varimax(A,normalize=FALSE,eps=1e-7,maxit=10000,randomStarts=20))
  Phi <- if (is.null(rot$Phi)) diag(ncol(A)) else rot$Phi
  aligned <- efa_align(unclass(rot$loadings),Phi,reference)
  c(aligned,list(converged=isTRUE(rot$convergence),rotation=rot))
}

efa_discrepancy <- function(S,Sigma) {
  p <- nrow(S)
  as.numeric(determinant(Sigma,logarithm=TRUE)$modulus + sum(diag(solve(Sigma,S))) -
    determinant(S,logarithm=TRUE)$modulus - p)
}

run_efa_analysis <- function(data_dir=".") {
  for (p in c("psych","GPArotation","digest"))
    if (!requireNamespace(p,quietly=TRUE)) stop("Required package: ",p)
  input <- efa_read_development(data_dir)
  x <- input$x; n <- nrow(x); p <- ncol(x); R <- cor(x); S <- cov(x)
  pa <- efa_permutation_pa(x)
  fits <- lapply(1:5,function(m) efa_extract(R,n,m))
  # psych does not expose its ML optimizer convergence flag. Independently
  # check the same likelihood optimum using stats::factanal (five starts).
  set.seed(20260927L)
  optimizer_checks <- lapply(1:5,function(m)
    stats::factanal(covmat=R,n.obs=n,factors=m,rotation="none",control=list(nstart=5)))
  rotations <- lapply(1:5,function(m) efa_rotate(unclass(fits[[m]]$fit$loadings),seed=20260925L+m))
  primary <- rotations[[3]]
  A <- unclass(fits[[3]]$fit$loadings)
  varimax <- efa_rotate(A,"varimax",reference=primary$P)
  geomin <- efa_rotate(A,"geomin",seed=20260926L,reference=primary$P)
  minres <- efa_extract(R,n,3,"minres")
  minres_rot <- efa_rotate(unclass(minres$fit$loadings),seed=20260926L,reference=primary$P)
  describe_fit <- function(f,m,rot) {
    common <- tcrossprod(unclass(f$loadings))
    Sigma <- common + diag(f$uniquenesses)
    residual <- R-Sigma
    Fml <- efa_discrepancy(R,Sigma)
    df <- ((p-m)^2-p-m)/2
    multiplier <- n-1-(2*p+5)/6-2*m/3
    data.frame(Factors=m,df=df,F_ML=Fml,Chi_square=multiplier*Fml,
      p_value=pchisq(multiplier*Fml,df,lower.tail=FALSE),
      RMS_offdiag=sqrt(mean(residual[lower.tri(residual)]^2)),
      Max_residual=max(abs(residual[lower.tri(residual)])),
      Min_uniqueness=min(f$uniquenesses),
      Optimizer_check=isTRUE(optimizer_checks[[m]]$converged),
      Objective_gap=abs(Fml-unname(optimizer_checks[[m]]$criteria["objective"])),Rotated=rot$converged,
      Boundary=min(f$uniquenesses)<=.0051)
  }
  candidates <- do.call(rbind,lapply(1:5,function(m) describe_fit(fits[[m]]$fit,m,rotations[[m]])))
  common <- primary$P %*% primary$Phi %*% t(primary$P)
  h2 <- diag(common); u2 <- fits[[3]]$fit$uniquenesses
  reproduced <- common+diag(u2); residual <- R-reproduced
  index <- which(lower.tri(residual),arr.ind=TRUE)
  residual_pairs <- data.frame(Item1=rownames(R)[index[,1]],Item2=colnames(R)[index[,2]],
    Observed=R[index],Reproduced=reproduced[index],Residual=residual[index])
  residual_pairs <- residual_pairs[order(abs(residual_pairs$Residual),decreasing=TRUE),]
  inverse <- solve(R); partial <- -cov2cor(inverse); diag(partial) <- 0
  kmo <- sum(R[lower.tri(R)]^2)/(sum(R[lower.tri(R)]^2)+sum(partial[lower.tri(partial)]^2))
  bartlett <- -(n-1-(2*p+5)/6)*as.numeric(determinant(R,logarithm=TRUE)$modulus)
  audit <- data.frame(Item=names(x),Mean=vapply(x,mean,numeric(1)),SD=vapply(x,sd,numeric(1)),
    Min=vapply(x,min,numeric(1)),Max=vapply(x,max,numeric(1)),
    Skew=vapply(x,function(z) mean((z-mean(z))^3)/mean((z-mean(z))^2)^1.5,numeric(1)),
    Missing=vapply(x,function(z) sum(is.na(z)),integer(1)))
  sensitivity <- do.call(rbind,lapply(list(ML_oblimin=primary,ML_geomin=geomin,Minres_oblimin=minres_rot),
    function(z) data.frame(Max_pattern_difference=max(abs(z$P-primary$P)),
      Max_Phi_difference=max(abs(z$Phi-primary$Phi)),
      Min_congruence=min(colSums(z$P*primary$P)/sqrt(colSums(z$P^2)*colSums(primary$P^2))))))
  rownames(sensitivity) <- c("ML oblimin","ML geomin","Minres oblimin")
  # A single donor-aligned PAF update, separate from ML and the PA target.
  reduced <- R; diag(reduced) <- 1-1/diag(solve(R))
  ev <- eigen(reduced,symmetric=TRUE)
  paf1 <- ev$vectors[,1:3]%*%diag(sqrt(ev$values[1:3]))
  result <- list(input=input,n=n,p=p,R=R,S=S,pa=pa,fits=fits,rotations=rotations,
    primary=primary,varimax=varimax,geomin=geomin,minres=minres,minres_rot=minres_rot,
    candidates=candidates,optimizer_checks=optimizer_checks,common=common,h2=h2,u2=u2,reproduced=reproduced,residual=residual,
    structure=primary$P%*%primary$Phi,residual_pairs=residual_pairs,kmo=kmo,bartlett=bartlett,
    audit=audit,sensitivity=sensitivity,paf_update=data.frame(Item=names(x),
      SMC=diag(reduced),First_update=rowSums(paf1^2)),
    versions=vapply(c("psych","GPArotation","digest"),function(p) as.character(packageVersion(p)),character(1)))
  result
}

# ---- verify efa results ----

# Source-safe checks for Chapter 2; no confirmation or revalidation data access.
verify_efa_results <- function(z) {
  checks <- list()
  add <- function(name,value) checks[[name]] <<- isTRUE(value)
  add("A only",identical(z$input$manifest$sample,"A"))
  add("360 by 12",identical(dim(z$input$x),c(360L,12L)))
  add("PA finite",all(is.finite(z$pa$null)))
  add("PA no failures",z$pa$failures==0L)
  add("moment counts",all(z$candidates$df==c(54,43,33,24,16)))
  add("independent optimizer convergence",all(z$candidates$Optimizer_check))
  add("independent ML objective",max(z$candidates$Objective_gap)<1e-6)
  add("rotation convergence",all(z$candidates$Rotated))
  add("primary admissible",min(z$u2)>0 && min(eigen(z$primary$Phi,symmetric=TRUE)$values)>0)
  add("structure",max(abs(z$structure-z$primary$P%*%z$primary$Phi))<1e-10)
  add("communalities",max(abs(z$h2-diag(z$common)))<1e-10)
  add("diagonal reconstruction",max(abs(z$h2+z$u2-1))<1e-6)
  add("residual identity",max(abs(z$R-z$reproduced-z$residual))<1e-12)
  A <- unclass(z$fits[[3]]$fit$loadings)
  for (name in c("primary","varimax","geomin")) {
    rot <- z[[name]]
    add(paste("rotation invariance",name),max(abs(rot$P%*%rot$Phi%*%t(rot$P)-tcrossprod(A)))<1e-6)
  }
  for (m in 1:5)
    add(paste("ML statistic",m),abs(z$candidates$Chi_square[m]-z$fits[[m]]$fit$STATISTIC)<1e-5)
  add("KMO",abs(z$kmo-psych::KMO(z$R)$MSA)<1e-10)
  add("Bartlett",abs(z$bartlett-psych::cortest.bartlett(z$R,z$n)$chisq)<1e-8)
  values <- unlist(checks)
  if(!all(values)) stop("Failed: ",paste(names(values)[!values],collapse=", "))
  values
}

# ---- freeze candidate ----

# Freeze once, after Sample A analysis and before any Sample B analysis.
freeze_sle_candidate <- function(data_dir=".",
                                path="chapter_02_frozen_candidate.rds") {
  if (file.exists(path)) stop("Candidate already frozen; refusing overwrite.")
  book <- sle_codebook()
  manifest <- sle_manifest()
  sle_read_sample("development",data_dir)
  primary <- paste("Planning =~ p1*P1 + p2*P2 + P3 + P4",
    "Strategy =~ S1 + S2 + S3 + S4 + P4",
    "Belonging =~ B1 + B2 + B3 + B4 + S4",sep="\n")
  simple <- paste("Planning =~ p1*P1 + p2*P2 + P3 + P4",
    "Strategy =~ S1 + S2 + S3 + S4",
    "Belonging =~ B1 + B2 + B3 + B4",sep="\n")
  candidate <- list(version="SLE-candidate-v1",frozen_on="2026-09-04",
    active_items=book$item,factors=c("Planning","Strategy","Belonging"),
    syntax=primary,
    rivals=list(M0_simple=simple,M1_cross=primary,
      M2_orthogonal=paste(primary,"Planning ~~ 0*Strategy + 0*Belonging\nStrategy ~~ 0*Belonging",sep="\n"),
      M3_equal=paste(primary,"p1 == p2",sep="\n"),
      M4_one=paste("General =~",paste(book$item,collapse=" + "))),
    free_parameters=c(M0_simple=27,M1_cross=29,M2_orthogonal=26,M3_equal=28,M4_one=24),
    df=c(M0_simple=51,M1_cross=49,M2_orthogonal=52,M3_equal=50,M4_one=54),
    settings=list(estimator="ML",likelihood="normal",std.lv=TRUE,meanstructure=FALSE),
    codebook_sha256=unique(manifest$codebook_sha256),population=unique(manifest$population),
    development_sha256=manifest$legacy_sha256[manifest$sample=="A"],
    secondary_loadings=c("P4 on Strategy","S4 on Belonging"),
    rationale="Pre-recorded item content plus stable Sample A secondary relations; no .30 cutoff, no item exclusions, no residual covariance freed.",
    history="A only used for development. B and C not analyzed before this freeze.")
  stopifnot(length(candidate$active_items)==12L,anyDuplicated(candidate$active_items)==0L)
  saveRDS(candidate,path,version=3)
  invisible(candidate)
}

# ---- render helpers ----

# Reusable, source-safe base-R graphics and tables for the Part Two chapters.
# No data access, file writes, package installation, or fitted-model creation.
pt2_table <- function(x, digits=3, caption=NULL, row.names=FALSE) {
  x <- as.data.frame(x,check.names=FALSE)
  integer_columns <- c("df","Df","Factors","Moments","Free","npar","Dimension",
    "Effective_parameters","Candidate_df","Delta_df","Missing")
  for(nm in names(x)) if(is.numeric(x[[nm]])) {
    d <- if(nm %in% integer_columns) 0 else digits
    x[[nm]] <- formatC(x[[nm]],digits=d,format="f")
  }
  names(x) <- gsub("_"," ",names(x),fixed=TRUE)
  out <- knitr::kable(x,caption=caption,row.names=row.names,booktabs=TRUE,longtable=FALSE)
  if(knitr::is_latex_output()) knitr::asis_output(paste0(
    "\\Needspace{",min(nrow(x)+7,25),"\\baselineskip}\n\n",
    paste(out,collapse="\n"),"\n\n")) else out
}
# Wrapped reference tables for the student-facing SLE appendix.
pt2_sle_appendix_table <- function(x,widths) {
  stopifnot(ncol(x)==length(widths))
  if(!knitr::is_latex_output()) return(knitr::kable(x,row.names=FALSE))
  out <- knitr::kable(x,format="latex",booktabs=TRUE,longtable=TRUE,
    align=rep("l",ncol(x)),row.names=FALSE,linesep="")
  old <- paste0("\\begin{longtable}{",paste(rep("l",ncol(x)),collapse=""),"}")
  columns <- paste0("p{",widths,"\\linewidth}",collapse="")
  out <- sub(old,paste0("\\begin{longtable}{@{}",columns,"@{}}"),out,fixed=TRUE)
  knitr::asis_output(paste0("\\begingroup\\small\n",out,"\n\\endgroup\n"))
}
pt2_num <- function(x,digits=3) formatC(x,digits=digits,format="f")
pt2_p <- function(x) ifelse(x<.001,"< .001",paste0("= ",pt2_num(x)))
pt2_heatmap <- function(M,title="",limit=max(abs(M)),digits=NULL,cex=.7) {
  nr <- nrow(M); nc <- ncol(M)
  par(mar=c(4,4,.9,1))
  palette <- grDevices::colorRampPalette(c("#8c510a","#f7f7f7","#2166ac"))(101)
  image(1:nc,1:nr,t(M[nr:1,,drop=FALSE]),zlim=c(-limit,limit),
        col=palette,axes=FALSE,xlab="",ylab="",main=title)
  axis(1,at=1:nc,labels=colnames(M),las=2,cex.axis=cex)
  axis(2,at=1:nr,labels=rev(rownames(M)),las=2,cex.axis=cex)
  if (!is.null(digits)) for (i in 1:nr) for (j in 1:nc) if(is.finite(M[i,j]))
    text(j,nr+1-i,formatC(M[i,j],digits=digits,format="f"),
         cex=cex*.8,col=if(abs(M[i,j])>limit*.6) "white" else "black")
  box()
}
pt2_pa_plot <- function(pa) {
  par(mfrow=c(1,2),mar=c(4,4,2,1))
  for (j in 1:2) {
    ylim <- range(c(pa$observed[,j],pa$reference[,j]))
    plot(1:nrow(pa$observed),pa$observed[,j],type="b",pch=16,ylim=ylim,
      xlab="Ordered dimension",ylab="Eigenvalue",
      main=c("Full Pearson matrix","SMC-reduced matrix")[j],cex.main=.95)
    lines(1:nrow(pa$observed),pa$reference[,j],lty=2,lwd=2,col="#9c5600")
    abline(h=0,col="gray80")
    legend("topright",c("Observed","Permutation 95th percentile"),
      lty=c(1,2),pch=c(16,NA),col=c("black","#9c5600"),bty="n",cex=.65)
  }
}
pt2_neighbor_plot <- function(z) {
  par(mfrow=c(1,3))
  for (m in 2:4) {
    P <- z$rotations[[m]]$P
    colnames(P) <- paste0("F",1:m)
    pt2_heatmap(P,paste(m,"ML factors"),limit=1,digits=2,cex=.8)
  }
}
pt2_rotation_plot <- function() {
  A <- rbind(c(.8,0),c(.7,.1),c(0,.6),c(.1,.7))
  Q <- matrix(c(1,1,-1,1),2,2)/sqrt(2)
  T <- matrix(c(1,0,.5,1),2,2)
  sets <- list(A,A%*%Q,A%*%solve(T))
  par(mfrow=c(1,3),mar=c(4,3,2,1))
  for (k in 1:3) {
    plot(sets[[k]],xlim=c(-.3,1.1),ylim=c(-.8,1),pch=16,
      xlab="Loading coordinate 1",ylab="Loading coordinate 2",
      main=c("Original","Orthogonal Q","Inverse-paired T")[k],cex.main=.9)
    abline(h=0,v=0,col="gray70")
    text(sets[[k]],labels=paste0("Y",1:4),pos=3,cex=.7)
  }
}
pt2_course_map <- function(labels) {
  n <- length(labels); par(mar=c(0,0,0,0))
  plot.new(); plot.window(xlim=c(0,n),ylim=c(0,1))
  for(i in seq_len(n)) {
    rect(i-.95,.25,i-.15,.75,col="#edf2f5",border="#405768")
    text(i-.55,.5,labels[i],cex=.8)
    if(i<n) arrows(i-.13,.5,i+.03,.5,length=.08)
  }
}
pt2_sle_diagram <- function(cross=TRUE,residual_pair=NULL,title="") {
  par(mar=c(1,1,2,1))
  plot.new(); plot.window(xlim=c(-2.5,8),ylim=c(0,13))
  title(main=title,cex.main=1)
  fy <- c(10.5,6.5,2.5); iy <- 12:1
  groups <- rep(1:3,each=4); ids <- c(paste0("P",1:4),paste0("S",1:4),paste0("B",1:4))
  for(g in 1:3) {
    symbols(0,fy[g],circles=.65,inches=FALSE,add=TRUE,bg="#e1ebf0",fg="#405768")
    text(0,fy[g],c("Planning","Strategy","Belonging")[g],cex=.65)
  }
  for(i in 1:12) {
    rect(5.2,iy[i]-.3,6.2,iy[i]+.3,col="#f7f3e8",border="#405768")
    text(5.7,iy[i],ids[i],cex=.8)
    arrows(.65,fy[groups[i]],5.15,iy[i],length=.06,col="#405768")
    arrows(7.25,iy[i],6.25,iy[i],length=.06,col="gray45")
    text(7.5,iy[i],paste0("e",i),cex=.65)
  }
  if(cross) {
    arrows(.65,fy[2],5.15,iy[4],length=.06,lty=2,lwd=1.5,col="#9c5600")
    arrows(.65,fy[3],5.15,iy[8],length=.06,lty=2,lwd=1.5,col="#9c5600")
  }
  for(pair in list(c(1,2),c(2,3),c(1,3))) {
    x <- if(identical(pair,c(1,3))) -2 else -1.25
    y <- fy[pair]
    segments(-.65,y[1],x,y[1],col="gray45")
    arrows(x,y[1],x,y[2],code=3,length=.05,col="gray45")
    segments(x,y[2],-.65,y[2],col="gray45")
  }
  if (!is.null(residual_pair)) {
    ix <- match(residual_pair,ids)
    arrows(7.9,iy[ix[1]],7.9,iy[ix[2]],code=3,length=.05,lty=3,lwd=2)
  }
}

