# QMSBR Part Two, Chapter 3: analysis, verification, and render helpers.
# Canonical companion to chapter_03.qmd; source from materials/part-two.
# Sourcing defines functions only. Generation/freezing require explicit calls;
# existing canonical data and sealed model objects must never be overwritten.

# ---- fit cfa models ----

# Continuous CFA specification, numerical audit, and exact Chapter 4 handoff.
# No package installation, archive reads, or Sample C reads.
pt3_microcase <- function(cross=0) {
  Lambda <- matrix(c(1,.8,1.2,0,0,0,0,0,cross,1,1.1,.9),6,2)
  dimnames(Lambda) <- list(paste0("Y",1:6),c("F1","F2"))
  Phi <- matrix(c(4,1.2,1.2,9),2,2,dimnames=list(colnames(Lambda),colnames(Lambda)))
  Theta <- diag(c(2,3,4,3,4,5)); dimnames(Theta) <- list(rownames(Lambda),rownames(Lambda))
  nu <- c(10,12,11,15,14,13)
  Sigma <- Lambda%*%Phi%*%t(Lambda)+Theta
  list(Lambda=Lambda,Phi=Phi,Theta=Theta,nu=nu,Sigma=Sigma)
}

pt3_generate_microcase <- function(path="chapter_03_donor_continuous.csv") {
  if(file.exists(path) || file.exists("chapter_03_donor_registry.rds"))
    stop("Continuous microcase or registry already exists; refusing overwrite.")
  pop <- pt3_microcase(cross=.25)
  RNGkind("Mersenne-Twister","Inversion","Rejection"); set.seed(20260930L)
  n <- 500L
  eta <- matrix(rnorm(n*2),n,2)%*%chol(pop$Phi)
  epsilon <- matrix(rnorm(n*6),n,6)%*%chol(pop$Theta)
  x <- sweep(eta%*%t(pop$Lambda)+epsilon,2,pop$nu,"+")
  colnames(x) <- rownames(pop$Lambda)
  write.csv(data.frame(id=sprintf("D%03d",seq_len(n)),x),path,row.names=FALSE)
  registry <- list(id="D-continuous-v1",n=n,seed=20260930L,population=pop,
    sha256=digest::digest(file=path,algo="sha256"),
    role="Separate synthetic continuous donor microcase; never Sample A, B, or C.",
    models=list(D1="F1 =~ Y1 + Y2 + Y3\nF2 =~ Y4 + Y5 + Y6",
      D2="F1 =~ Y1 + Y2\nF2 =~ Y3 + Y4 + Y5 + Y6",
      D3="F1 =~ Y1 + Y2 + Y3\nF2 =~ Y4 + Y5 + Y6 + Y3",
      D4="F1 =~ Y1 + Y2 + Y3\nF2 =~ Y4 + Y5 + Y6 + Y3\nF1 ~~ 0*F2"),
    settings=list(estimator="ML",likelihood="normal",std.lv=TRUE,meanstructure=FALSE),
    restrictions="All unspecified loadings and residual covariances fixed zero; residual variances free; D4 factor covariance fixed zero; other factor covariances free; no equalities.",
    analytic_status="D1-D4 specified before microcase generation; numerical teaching comparisons only.")
  saveRDS(registry,"chapter_03_donor_registry.rds",version=3)
}

pt3_read_sample <- function(role,data_dir=".",candidate) {
  stopifnot(role %in% c("confirmation","revalidation"))
  source(file.path(data_dir,"chapter_02.R"),
    local=TRUE)
  input <- sle_read_sample(role,data_dir)
  stopifnot(input$manifest$population=="SLE-continuous-v1",
    input$manifest$codebook_sha256==candidate$codebook_sha256,
    input$manifest_all$legacy_sha256[input$manifest_all$sample=="A"]==
      candidate$development_sha256,
    identical(candidate$active_items,input$book$item))
  input
}

pt3_fit <- function(syntax,x,std.lv=TRUE,meanstructure=FALSE) {
  warns <- character()
  fit <- withCallingHandlers(lavaan::cfa(syntax,data=x,estimator="ML",
    likelihood="normal",std.lv=std.lv,meanstructure=meanstructure,
    missing="listwise",se="standard",test="standard",information="expected"),
    warning=function(w) { warns <<- c(warns,conditionMessage(w)); invokeRestart("muffleWarning") })
  list(fit=fit,warnings=warns)
}

pt3_audit <- function(record,items=NULL) {
  fit <- record$fit; opt <- lavaan::lavInspect(fit,"options")
  est <- lavaan::lavInspect(fit,"est"); Sigma <- lavaan::fitted(fit)$cov
  if(is.null(items)) items <- lavaan::lavNames(fit,"ov")
  pt <- lavaan::parTable(fit)
  # Effective free coordinates: raw free slots less the rank of equality rows.
  eq <- pt[pt$op=="==",,drop=FALSE]
  nfree <- length(unique(pt$free[pt$free>0]))-nrow(eq)
  u <- length(items)*(length(items)+1)/2+if(opt$meanstructure) length(items) else 0
  Delta <- lavaan::lavInspect(fit,"delta")
  out <- c(Converged=isTRUE(lavaan::lavInspect(fit,"converged")),
    No_warnings=length(record$warnings)==0L,
    Positive_residual_variances=all(diag(est$theta)>0),
    Positive_factor_covariance=min(eigen(est$psi,symmetric=TRUE)$values)>1e-8,
    Positive_implied_covariance=min(eigen(Sigma,symmetric=TRUE)$values)>1e-8,
    ML=opt$estimator=="ML",Normal=opt$likelihood=="normal",
    Expected_information=all(opt$information=="expected"),
    Standard_errors=opt$se=="standard",Complete=opt$missing=="listwise",
    Item_order=identical(lavaan::lavNames(fit,"ov"),items),
    Count=abs(u-nfree-lavaan::fitMeasures(fit,"df"))<1e-8)
  list(checks=out,nfree=nfree,moments=u,df=u-nfree,
    delta_rank=qr(Delta,tol=1e-7)$rank,delta_columns=ncol(Delta),
    max_gradient=max(abs(lavaan::lavInspect(fit,"gradient"))),
    min_information_eigen=min(eigen(lavaan::lavInspect(fit,"information"),symmetric=TRUE)$values),
    min_residual=min(diag(est$theta)),min_phi_eigen=min(eigen(est$psi,symmetric=TRUE)$values),
    options=opt,parameters=lavaan::parameterEstimates(fit,standardized=TRUE),
    matrices=est,Sigma=Sigma,vcov=lavaan::vcov(fit))
}

pt3_build <- function() {
  candidate_path <- "chapter_02_frozen_candidate.rds"
  stopifnot(file.exists(candidate_path))
  candidate <- readRDS(candidate_path)
  input <- pt3_read_sample("confirmation",candidate=candidate)
  primary <- pt3_fit(candidate$syntax,input$x)
  audit <- pt3_audit(primary,candidate$active_items)
  stopifnot(all(audit$checks),audit$nfree==29,audit$df==49,
    audit$delta_rank==audit$delta_columns)
  marker <- pt3_fit(candidate$syntax,input$x,std.lv=FALSE)
  means <- pt3_fit(candidate$syntax,input$x,meanstructure=TRUE)
  simple_means <- pt3_fit(candidate$rivals$M0_simple,input$x,meanstructure=TRUE)
  stopifnot(all(pt3_audit(marker)$checks),all(pt3_audit(means)$checks),
    all(pt3_audit(simple_means)$checks),
    max(abs(lavaan::fitted(marker$fit)$cov-audit$Sigma))<1e-3,
    max(abs(lavaan::fitted(means$fit)$cov-audit$Sigma))<1e-3,
    max(abs(lavaan::fitted(means$fit)$mean-colMeans(input$x)))<1e-5)
  fit_measure_names <- c("chisq","df","pvalue","rmsea","rmsea.ci.lower","rmsea.ci.upper",
    "cfi","tli","srmr","logl","aic","bic","baseline.chisq","baseline.df")
  measures <- lavaan::fitMeasures(primary$fit,fit_measure_names)
  stopifnot(all(is.finite(measures)))
  pop <- pt3_microcase()
  stopifnot(abs(pop$Sigma[2,3]-.8*1.2*4)<1e-12,
    abs(pop$Sigma[2,5]-.8*1.1*1.2)<1e-12)
  D <- diag(1/sqrt(diag(pop$Phi)))
  scaled <- list(Lambda=pop$Lambda%*%solve(D),Phi=D%*%pop$Phi%*%D)
  stopifnot(max(abs(scaled$Lambda%*%scaled$Phi%*%t(scaled$Lambda)+pop$Theta-pop$Sigma))<1e-12)
  registry <- readRDS("chapter_03_donor_registry.rds")
  donor_path <- "chapter_03_donor_continuous.csv"
  donor_x <- read.csv(donor_path)[paste0("Y",1:6)]
  donor <- pt3_fit(registry$models$D1,donor_x)
  donor_marker <- pt3_fit(registry$models$D1,donor_x,std.lv=FALSE)
  stopifnot(all(pt3_audit(donor)$checks),all(pt3_audit(donor_marker)$checks),
    max(abs(lavaan::fitted(donor$fit)$cov-lavaan::fitted(donor_marker$fit)$cov))<1e-4)
  list(version="SLE-CFA-handoff-v1",candidate=candidate,
    candidate_sha256=digest::digest(file=candidate_path,algo="sha256"),
    input=input,fit=primary$fit,warnings=primary$warnings,audit=audit,
    marker=marker,means=means,simple_means=simple_means,
    fit_measure_names=fit_measure_names,measures=measures,
    S_N=unclass(lavaan::lavInspect(primary$fit,"sampstat")$cov),
    parameter_table=lavaan::parTable(primary$fit),
    wald=lavaan::lavTestWald(primary$fit,"p1 == p2"),
    microcase=pop,scaled=scaled,donor=donor,donor_marker=donor_marker,
    donor_registry=registry,
    metadata=list(R=as.character(getRversion()),lavaan=as.character(packageVersion("lavaan")),
      created="2026-09-04",sample="B",role="confirmation",
      status="Estimation only; Chapter 3 does not assess model adequacy.",
      sample_C="Not read during Chapter 3 construction."))
}

# ---- render helpers ----

pt3_estimation_plot <- function() {
  par(mar=c(1,1,1,1));plot.new();plot.window(xlim=c(0,10),ylim=c(0,5))
  t <- seq(1,8,length.out=150); y <- 1+.08*(t-4)^2
  lines(t,y,lwd=2,col="#405768")
  points(5,4,pch=16);text(5,4.4,"Observed moments S",cex=.9)
  points(4.5,1.02,pch=17,col="#9c5600");text(6.6,.45,"Selected implied moments",cex=.85)
  arrows(5,3.8,4.5,1.25,length=.09,lty=2)
  text(2,2.6,"Restricted model\nset of moments",cex=.85)
  text(7.7,3,"ML discrepancy;\nnot Euclidean distance",cex=.8)
}
