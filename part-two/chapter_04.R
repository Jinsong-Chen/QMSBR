# QMSBR Part Two, Chapter 4: analysis, verification, and render helpers.
# Canonical companion to chapter_04.qmd; source from materials/part-two.
# Sourcing defines functions only. Generation/freezing require explicit calls;
# existing canonical data and sealed model objects must never be overwritten.

# ---- evaluate cfa ----

# Chapter 4 consumes the exact Chapter 3 fit. It never refits primary B.
pt4_rmsea_ci <- function(T,df,n,level=.90) {
  targets <- c((1+level)/2,(1-level)/2)
  ncp <- vapply(targets,function(prob) {
    if(pchisq(T,df,ncp=0)<=prob) return(0)
    upper <- max(1,T)
    while(pchisq(T,df,ncp=upper)>prob) upper <- upper*2
    uniroot(function(delta)pchisq(T,df,ncp=delta)-prob,c(0,upper),tol=1e-9)$root
  },numeric(1))
  sqrt(ncp/(n*df))
}
pt4_handoff <- function() {
  path <- "chapter_03_chapter_04_handoff.rds"
  h <- readRDS(path)
  stopifnot(h$metadata$sample=="B",h$metadata$lavaan==as.character(packageVersion("lavaan")),
    h$candidate_sha256==digest::digest(file="chapter_02_frozen_candidate.rds",algo="sha256"))
  input <- pt3_read_sample("confirmation",candidate=h$candidate)
  stopifnot(identical(input$x,h$input$x),all(h$audit$checks))
  h
}
pt4_profile <- function(record) {
  f <- record$fit; a <- pt3_audit(record)
  stopifnot(all(a$checks))
  n <- lavaan::lavInspect(f,"nobs"); p <- length(lavaan::lavNames(f,"ov"))
  fm <- lavaan::fitMeasures(f,c("chisq","df","pvalue","rmsea","rmsea.ci.lower",
    "rmsea.ci.upper","cfi","tli","srmr","logl","aic","bic","baseline.chisq","baseline.df","npar"))
  S <- unclass(lavaan::lavInspect(f,"sampstat")$cov); Sig <- lavaan::fitted(f)$cov
  E <- S-Sig; Es <- E/sqrt(outer(diag(S),diag(S))); Er <- cov2cor(S)-cov2cor(Sig)
  Fml <- as.numeric(determinant(Sig,logarithm=TRUE)$modulus+sum(diag(solve(Sig,S)))-
    determinant(S,logarithm=TRUE)$modulus-p)
  rmsea <- sqrt(max((fm["chisq"]-fm["df"])/(n*fm["df"]),0))
  cfi <- 1-max(fm["chisq"]-fm["df"],0)/max(fm["chisq"]-fm["df"],fm["baseline.chisq"]-fm["baseline.df"],0)
  tli <- (fm["baseline.chisq"]/fm["baseline.df"]-fm["chisq"]/fm["df"])/
    (fm["baseline.chisq"]/fm["baseline.df"]-1)
  srmr <- sqrt(mean(Es[lower.tri(Es,diag=TRUE)]^2))
  stopifnot(abs(n*Fml-fm["chisq"])<1e-5,abs(rmsea-fm["rmsea"])<1e-8,
    abs(cfi-fm["cfi"])<1e-8,abs(tli-fm["tli"])<1e-8,
    abs(srmr-fm["srmr"])<1e-6,
    abs(-2*fm["logl"]+2*fm["npar"]-fm["aic"])<1e-6,
    abs(-2*fm["logl"]+log(n)*fm["npar"]-fm["bic"])<1e-6)
  stopifnot(max(abs(pt4_rmsea_ci(fm["chisq"],fm["df"],n)-
    fm[c("rmsea.ci.lower","rmsea.ci.upper")]))<1e-5)
  ix <- which(lower.tri(Es),arr.ind=TRUE)
  pairs <- data.frame(Item1=rownames(S)[ix[,1]],Item2=colnames(S)[ix[,2]],
    Observed=S[ix],Implied=Sig[ix],Raw=E[ix],Std=Es[ix],Correlation=Er[ix])
  pairs <- pairs[order(abs(pairs$Std),decreasing=TRUE),]
  list(record=record,audit=a,measures=fm,S=S,Sigma=Sig,E=E,Es=Es,Er=Er,
    pairs=pairs,Fml=Fml,n=n,p=p,manual_srmr=srmr,
    MI=if(any(lavaan::parTable(f)$op=="==")) NULL else lavaan::modindices(f,sort.=TRUE),
    parameters=lavaan::parameterEstimates(f,standardized=TRUE))
}
pt4_lr <- function(restricted,unrestricted) {
  stopifnot(identical(lavaan::lavNames(restricted,"ov"),lavaan::lavNames(unrestricted,"ov")),
    lavaan::lavInspect(restricted,"nobs")==lavaan::lavInspect(unrestricted,"nobs"))
  test <- lavaan::lavTestLRT(unrestricted,restricted,method="standard")
  T <- lavaan::fitMeasures(restricted,"chisq")-lavaan::fitMeasures(unrestricted,"chisq")
  df <- lavaan::fitMeasures(restricted,"df")-lavaan::fitMeasures(unrestricted,"df")
  stopifnot(df>0,T>=-1e-6,abs(tail(test[["Chisq diff"]],1)-T)<1e-6)
  c(Delta_T=unname(T),Delta_df=unname(df),p=unname(pchisq(T,df,lower.tail=FALSE)))
}
pt4_analyze_B <- function() {
  h <- pt4_handoff()
  records <- lapply(h$candidate$rivals[names(h$candidate$rivals)!="M1_cross"],function(s)pt3_fit(s,h$input$x))
  # The primary B model is the exact inherited object, never a new fit.
  records$M1_cross <- list(fit=h$fit,warnings=h$warnings)
  records <- records[names(h$candidate$rivals)]
  profiles <- lapply(records,pt4_profile)
  # This didactic residual equality is not promoted to an A-frozen rival.
  vsyntax <- paste(h$candidate$syntax,"P1 ~~ v1*P1\nP2 ~~ v2*P2\nv1 == v2",sep="\n")
  variance_equal <- pt3_fit(vsyntax,h$input$x)
  vp <- pt4_profile(variance_equal)
  lr <- rbind(M0_vs_M1=pt4_lr(records$M0_simple$fit,h$fit),
    M2_vs_M1=pt4_lr(records$M2_orthogonal$fit,h$fit),
    M3_vs_M1=pt4_lr(records$M3_equal$fit,h$fit),
    V1_vs_M1=pt4_lr(variance_equal$fit,h$fit))
  donor_x <- read.csv("chapter_03_donor_continuous.csv")[paste0("Y",1:6)]
  donor <- lapply(h$donor_registry$models,function(s)pt3_fit(s,donor_x))
  donor_profiles <- lapply(donor,pt4_profile)
  # For D2 the model's order is Y1,Y2,Y3,Y4,Y5,Y6, as for the other D models.
  d_lr <- rbind(D1_vs_D3=pt4_lr(donor$D1$fit,donor$D3$fit),
    D2_vs_D3=pt4_lr(donor$D2$fit,donor$D3$fit),D4_vs_D3=pt4_lr(donor$D4$fit,donor$D3$fit))
  dmi <- subset(donor_profiles$D2$MI,lhs=="F1" & op=="=~" & rhs=="Y3")
  dp <- subset(donor_profiles$D3$parameters,lhs=="F1" & op=="=~" & rhs=="Y3")
  triangle <- data.frame(Test=c("Score (MI in D2)","Wald (D3 loading)","LR (D2 versus D3)"),
    Statistic=c(dmi$mi,(dp$est/dp$se)^2,d_lr["D2_vs_D3","Delta_T"]),df=1)
  list(h=h,profiles=profiles,lr=lr,variance_equal=vp,
    donor=donor_profiles,donor_lr=d_lr,triangle=triangle)
}

# These two measurement-model extensions are didactic Sample-B analyses.
# They were not members of the Sample-A-frozen M0--M4 registry and are never
# promoted to independent confirmation or searched again in Sample C.
pt4_extension_registry <- function(h) {
  higher_order <- paste(h$candidate$syntax,
    "General =~ Planning + Strategy + Belonging",sep="\n")
  bifactor <- paste(
    "General =~ P1 + P2 + P3 + P4 + S1 + S2 + S3 + S4 + B1 + B2 + B3 + B4",
    "Planning_s =~ P1 + P2 + P3 + P4",
    "Strategy_s =~ S1 + S2 + S3 + S4",
    "Belonging_s =~ B1 + B2 + B3 + B4",
    "General ~~ 0*Planning_s + 0*Strategy_s + 0*Belonging_s",
    "Planning_s ~~ 0*Strategy_s + 0*Belonging_s",
    "Strategy_s ~~ 0*Belonging_s",sep="\n")
  list(
    HO_SLE=list(syntax=higher_order,
      status="Didactic equivalent representation fitted after the frozen M1-cross analysis."),
    BIF_SLE=list(syntax=bifactor,
      status="Didactic nonnested rival fitted after the frozen M1-cross analysis; no Sample-C search."))
}

pt4_omega_h <- function(profile,weights,general="General") {
  est <- profile$audit$matrices
  stopifnot(general %in% colnames(est$lambda),length(weights)==nrow(est$lambda))
  lg <- est$lambda[,general,drop=FALSE]
  phigg <- est$psi[general,general]
  drop((t(weights)%*%lg)^2*phigg/(t(weights)%*%profile$Sigma%*%weights))
}

pt4_analyze_extensions <- function(b) {
  registry <- pt4_extension_registry(b$h)
  records <- lapply(registry,function(z)pt3_fit(z$syntax,b$h$input$x))
  profiles <- lapply(records,pt4_profile)
  primary <- b$profiles$M1_cross

  # On the standardized latent metric, three positive correlations determine
  # three second-order loadings whenever the solution is real and admissible.
  Phi <- cov2cor(primary$audit$matrices$psi)
  r12 <- Phi["Planning","Strategy"]
  r13 <- Phi["Planning","Belonging"]
  r23 <- Phi["Strategy","Belonging"]
  gamma <- c(Planning=sqrt(r12*r13/r23),
    Strategy=sqrt(r12*r23/r13),Belonging=sqrt(r13*r23/r12))
  disturbances <- 1-gamma^2
  stopifnot(all(is.finite(gamma)),all(disturbances>=0),
    max(abs(outer(gamma,gamma)[lower.tri(Phi)]-Phi[lower.tri(Phi)]))<1e-6,
    max(abs(profiles$HO_SLE$Sigma-primary$Sigma))<1e-3,
    abs(profiles$HO_SLE$measures["chisq"]-primary$measures["chisq"])<1e-5,
    profiles$HO_SLE$audit$nfree==29,profiles$HO_SLE$audit$df==49,
    profiles$BIF_SLE$audit$nfree==36,profiles$BIF_SLE$audit$df==42)

  bifactor_loadings <- subset(profiles$BIF_SLE$parameters,
    op=="=~" & lhs %in% c("General","Planning_s","Strategy_s","Belonging_s"),
    select=c(lhs,rhs,est,se,pvalue,std.all))
  names(bifactor_loadings) <- c("Factor","Item","Raw","SE","p","Std_all")
  weights <- rep(1,12)
  omega_total <- pt4_omega(profiles$BIF_SLE,weights)
  omega_h <- pt4_omega_h(profiles$BIF_SLE,weights)
  list(registry=registry,profiles=profiles,Phi=Phi,gamma=gamma,
    disturbances=disturbances,bifactor_loadings=bifactor_loadings,
    omega_total=omega_total,omega_h=omega_h,
    reliable_general_share=omega_h/omega_total)
}

# Retrospective known-population audit. This is deliberately downstream of the
# frozen B/C sequence; it does not alter, validate, or repair the primary model.
pt4_population_audit <- function(b,n=360L) {
  pop <- sle_population()
  Sigma0 <- pop$Lambda%*%pop$Phi%*%t(pop$Lambda)+pop$Theta
  warns <- character()
  fit <- withCallingHandlers(lavaan::cfa(b$h$candidate$syntax,
    sample.cov=Sigma0,sample.nobs=n,sample.cov.rescale=FALSE,
    estimator="ML",likelihood="normal",std.lv=TRUE,meanstructure=FALSE,
    se="none",test="standard",information="expected"),
    warning=function(w) { warns <<- c(warns,conditionMessage(w)); invokeRestart("muffleWarning") })
  stopifnot(isTRUE(lavaan::lavInspect(fit,"converged")),length(warns)==0L)
  Sigma_star <- unclass(lavaan::fitted(fit)$cov)
  p <- nrow(Sigma0); df <- unname(lavaan::fitMeasures(fit,"df"))
  discrepancy <- function(S,Sigma) as.numeric(
    determinant(Sigma,logarithm=TRUE)$modulus+sum(diag(solve(Sigma,S)))-
      determinant(S,logarithm=TRUE)$modulus-nrow(S))
  F0 <- discrepancy(Sigma0,Sigma_star)
  Find <- discrepancy(Sigma0,diag(diag(Sigma0)))
  Es <- (Sigma0-Sigma_star)/sqrt(outer(diag(Sigma0),diag(Sigma0)))
  population <- c(F0=F0,RMSEA=sqrt(F0/df),CFI=1-F0/Find,
    SRMR=sqrt(mean(Es[lower.tri(Es,diag=TRUE)]^2)))
  sample_formula <- lavaan::fitMeasures(fit,c("chisq","df","pvalue","rmsea","cfi","srmr"))

  pe <- lavaan::parameterEstimates(fit,standardized=TRUE)
  estimated <- subset(pe,lhs=="Belonging" & op=="=~" & rhs %in% paste0("B",1:4),
    select=c(rhs,std.all))
  estimated <- estimated[match(paste0("B",1:4),estimated$rhs),]
  displacement <- data.frame(Item=paste0("B",1:4),Generating=c(.80,.74,.67,.50),
    Pseudo_true=estimated$std.all)
  displacement$Displacement <- displacement$Pseudo_true-displacement$Generating

  R0 <- cov2cor(Sigma0); Rstar <- cov2cor(Sigma_star)
  tetrad0 <- R0["B1","B2"]*R0["B3","B4"]-
    R0["B1","B3"]*R0["B2","B4"]
  tetrad_star <- Rstar["B1","B2"]*Rstar["B3","B4"]-
    Rstar["B1","B3"]*Rstar["B2","B4"]
  stopifnot(abs(pop$Theta_z["B1","B2"]-.12)<1e-12,
    abs(population["RMSEA"]-.0153856)<1e-5,
    abs(population["CFI"]-.997289)<1e-5,
    abs(population["SRMR"]-.0108593)<1e-5,
    abs(tetrad0-0.0402)<1e-10,abs(tetrad_star)<1e-6)
  list(population=population,sample_formula=sample_formula,df=df,n=n,
    omitted_standardized_residual=pop$Theta_z["B1","B2"],
    omitted_raw_residual=pop$Theta["B1","B2"],
    tetrad=c(Generating=tetrad0,Imposed=tetrad_star),
    displacement=displacement,Sigma0=Sigma0,Sigma_star=Sigma_star)
}
pt4_freeze_revision <- function(b,path="chapter_04_frozen_revision.rds") {
  if(file.exists(path)) stop("Revision already frozen; refusing overwrite.")
  r <- list(id="R1-B4",source="B diagnosis only; tentative sensitivity, not an endorsed measurement revision",frozen_on="2026-09-04",
    parent="M1_cross",syntax=paste(b$h$candidate$syntax,"Planning =~ B4",sep="\n"),
    reason="B4 has several negative cross-domain residuals; Planning-on-B4 is the largest one-parameter MI. Institutional connection wording does not provide a compelling Planning mechanism, so this is deliberately tentative and not automatically adopted.",
    change="Free B4 loading on Planning; all items, other loadings/restrictions and ML settings unchanged.",
    df=48L,nfree=30L,candidate_sha256=b$h$candidate_sha256,
    handoff_sha256=digest::digest(file="chapter_03_chapter_04_handoff.rds",algo="sha256"),
    C_status="Sample C not read before this freeze; compare M1 and R1 on C without further search.")
  saveRDS(r,path,version=3); invisible(r)
}
pt4_revalidate <- function(b) {
  r <- readRDS("chapter_04_frozen_revision.rds")
  stopifnot(r$candidate_sha256==b$h$candidate_sha256,
    r$handoff_sha256==digest::digest(file="chapter_03_chapter_04_handoff.rds",algo="sha256"))
  revised_B <- pt4_profile(pt3_fit(r$syntax,b$h$input$x))
  stopifnot(revised_B$audit$df==r$df,revised_B$audit$nfree==r$nfree)
  input <- pt3_read_sample("revalidation",candidate=b$h$candidate)
  primary_C <- pt4_profile(pt3_fit(b$h$candidate$syntax,input$x))
  revised_C <- pt4_profile(pt3_fit(r$syntax,input$x))
  list(revision=r,revised_B=revised_B,input=input,primary_C=primary_C,revised_C=revised_C,
    lr_B=pt4_lr(b$h$fit,revised_B$record$fit),
    lr_C=pt4_lr(primary_C$record$fit,revised_C$record$fit))
}
pt4_omega <- function(profile,weights) {
  est <- profile$audit$matrices
  common <- est$lambda%*%est$psi%*%t(est$lambda)
  drop(t(weights)%*%common%*%weights/(t(weights)%*%profile$Sigma%*%weights))
}
pt4_scores <- function(profile,x) {
  est <- profile$audit$matrices; L <- est$lambda; Phi <- est$psi; Theta <- est$theta
  A <- Phi%*%t(L)%*%solve(profile$Sigma)
  posterior <- Phi-A%*%L%*%Phi
  Bartlett <- solve(t(L)%*%solve(Theta,L),t(L)%*%solve(Theta))
  centered <- scale(as.matrix(x),center=TRUE,scale=FALSE)
  regression <- centered%*%t(A); bartlett <- centered%*%t(Bartlett)
  list(regression=regression,bartlett=bartlett,posterior=posterior,
    determinacy=sqrt(diag(Phi-posterior)/diag(Phi)))
}

# ---- render helpers ----

pt4_fit_table <- function(profiles) {
  t <- do.call(rbind,lapply(profiles,function(p) {
    f <- p$measures
    data.frame(T=unname(f["chisq"]),df=unname(f["df"]),p=if(f["pvalue"]<.001) "<.001" else pt2_num(f["pvalue"]),
      RMSEA=unname(f["rmsea"]),CI90=paste0("[",pt2_num(f["rmsea.ci.lower"]),", ",pt2_num(f["rmsea.ci.upper"]),"]"),
      CFI=unname(f["cfi"]),TLI=unname(f["tli"]),SRMR=unname(f["srmr"]))
  }))
  data.frame(Model=rownames(t),t,row.names=NULL)
}
pt4_interval_plot <- function(profiles) {
  m <- do.call(rbind,lapply(profiles,function(p)p$measures[c("rmsea","rmsea.ci.lower","rmsea.ci.upper")]))
  par(mar=c(4,8,1,1));n <- nrow(m)
  plot(m[,1],n:1,xlim=c(0,max(m)*1.08),ylim=c(.5,n+.5),yaxt="n",pch=16,
    xlab="RMSEA (normal-likelihood convention)",ylab="")
  axis(2,at=n:1,labels=names(profiles),las=2,cex.axis=.8)
  segments(m[,2],n:1,m[,3],n:1,lwd=2,col="#405768")
  points(m[,1],n:1,pch=16,col="#9c5600")
}
pt4_donor_nesting <- function() {
  par(mar=c(0,0,0,0));plot.new();plot.window(xlim=c(0,10),ylim=c(0,5))
  rect(3.7,3.3,6.3,4.3,col="#e1ebf0");text(5,3.8,"D3: both Y3 loadings",cex=.85)
  for(i in 1:3) {
    x <- c(1.7,5,8.3)[i]
    rect(x-1.4,.5,x+1.4,1.6,col="#f7f3e8")
    text(x,1.05,c("D1: Y3 only on F1","D2: Y3 only on F2","D4: factors orthogonal")[i],cex=.75)
    arrows(5,3.2,x,1.7,length=.08)
    text((5+x)/2,2.25,c("lambda32 = 0","lambda31 = 0","phi12 = 0")[i],cex=.7)
  }
}
pt4_revision_plot <- function(c) {
  rows <- lapply(list(c$revised_B,c$revised_C),function(p)
    subset(p$parameters,lhs=="Planning" & op=="=~" & rhs=="B4"))
  est <- vapply(rows,function(z)z$est,numeric(1));lo <- vapply(rows,function(z)z$ci.lower,numeric(1));hi <- vapply(rows,function(z)z$ci.upper,numeric(1))
  par(mar=c(4,8,1,1));plot(est,2:1,xlim=range(c(lo,hi)),ylim=c(.5,2.5),yaxt="n",pch=16,
    xlab="Raw B4 loading on Planning, with 95% interval",ylab="")
  abline(v=0,lty=2,col="gray50");segments(lo,2:1,hi,2:1,lwd=2,col="#405768")
  axis(2,at=2:1,labels=c("B: developed here","C: frozen retest"),las=2,cex.axis=.8)
  points(est,2:1,pch=16,col="#9c5600")
}
